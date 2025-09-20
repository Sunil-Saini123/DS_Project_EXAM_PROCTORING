#!/usr/bin/env python3
"""
Ricart-Agrawala Service - Updated for unified system
Implements distributed mutual exclusion using Ricart-Agrawala algorithm
"""

import asyncio
import grpc
import logging
import threading
import time
from collections import deque, defaultdict
from concurrent import futures
from typing import Dict, Set, Optional

import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

# Configuration
RICART_AGRAWALA_PORT = 50052

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RicartAgrawala')

class RicartAgrawalaServiceServicer(pb2_grpc.RicartAgrawalaServiceServicer):
    """
    Implements the Ricart-Agrawala distributed mutual exclusion algorithm.
    Enhanced version with better request handling and priority support.
    """
    
    def __init__(self):
        # Request queue sorted by (timestamp, process_id)
        self.request_queue = deque()
        
        # Current state of critical sections
        self.critical_sections: Dict[str, dict] = {}
        
        # Waiting processes and their events
        self.waiting_processes: Dict[str, asyncio.Event] = {}
        
        # Thread-safe locks
        self.queue_lock = threading.RLock()
        self.cs_lock = threading.RLock()
        
        # Lamport logical clock
        self.logical_clock = 0
        self.clock_lock = threading.Lock()
        
        # Request tracking for debugging
        self.request_history: deque = deque(maxlen=1000)
        
        logger.info("Ricart-Agrawala Service initialized")
    
    def _update_logical_clock(self, received_timestamp: int = 0) -> int:
        """Update logical clock following Lamport's algorithm"""
        with self.clock_lock:
            self.logical_clock = max(self.logical_clock, received_timestamp) + 1
            return self.logical_clock
    
    def _get_resource_id(self, roll_no: str) -> str:
        """Extract resource identifier from roll_no"""
        # Handle different types of requests
        if roll_no.startswith("consistency_"):
            return roll_no.replace("consistency_", "")
        elif roll_no.startswith("teacher_"):
            return roll_no.replace("teacher_", "")
        elif roll_no.startswith("write_tx_"):
            return roll_no.replace("write_tx_", "")
        elif roll_no == "global_read_all":
            return "global_read_all"
        else:
            return roll_no
    
    async def RequestCS(self, request, context):
        """Handle critical section access request"""
        roll_no = request.roll_no
        timestamp = request.lamport_timestamp
        resource_id = self._get_resource_id(roll_no)
        
        # Update logical clock
        current_clock = self._update_logical_clock(timestamp)
        
        logger.info(f"[CS REQUEST] {roll_no} requesting access to resource '{resource_id}' at timestamp {timestamp}")
        
        # Add to request history
        self.request_history.append({
            'type': 'request',
            'roll_no': roll_no,
            'resource_id': resource_id,
            'timestamp': timestamp,
            'received_at': time.time()
        })
        
        with self.queue_lock:
            # Check if resource is already held
            if resource_id in self.critical_sections:
                cs_info = self.critical_sections[resource_id]
                holder = cs_info['holder']
                holder_timestamp = cs_info['timestamp']
                
                logger.info(f"[CS REQUEST] Resource '{resource_id}' held by {holder} (ts: {holder_timestamp})")
                
                # Compare timestamps for priority
                if timestamp < holder_timestamp or (timestamp == holder_timestamp and roll_no < holder):
                    # Higher priority - preempt current holder (not implemented for safety)
                    logger.warning(f"[CS REQUEST] {roll_no} has higher priority but preemption not implemented")
                
                # Add to waiting queue
                self.request_queue.append((timestamp, roll_no, resource_id, time.time()))
                self.request_queue = deque(sorted(self.request_queue, key=lambda x: (x[0], x[1])))
                
                # Create waiting event
                wait_event = asyncio.Event()
                self.waiting_processes[roll_no] = wait_event
                
                logger.info(f"[CS REQUEST] {roll_no} queued for resource '{resource_id}', queue size: {len(self.request_queue)}")
            else:
                # Resource is free - grant immediately
                self.critical_sections[resource_id] = {
                    'holder': roll_no,
                    'timestamp': timestamp,
                    'granted_at': time.time(),
                    'clock': current_clock
                }
                
                logger.info(f"[CS GRANTED] {roll_no} granted immediate access to resource '{resource_id}'")
                
                return pb2.RequestCSResponse(success=True)
        
        # Wait for resource to become available
        logger.info(f"[CS WAITING] {roll_no} waiting for resource '{resource_id}'...")
        
        try:
            # Wait with timeout to prevent infinite blocking
            await asyncio.wait_for(wait_event.wait(), timeout=60.0)
            
            logger.info(f"[CS GRANTED] {roll_no} granted access to resource '{resource_id}' after waiting")
            return pb2.RequestCSResponse(success=True)
            
        except asyncio.TimeoutError:
            logger.error(f"[CS TIMEOUT] {roll_no} timed out waiting for resource '{resource_id}'")
            
            # Clean up
            with self.queue_lock:
                if roll_no in self.waiting_processes:
                    del self.waiting_processes[roll_no]
                
                # Remove from queue
                self.request_queue = deque([
                    req for req in self.request_queue if req[1] != roll_no
                ])
            
            return pb2.RequestCSResponse(success=False)
    
    async def ReleaseCS(self, request, context):
        """Handle critical section release"""
        roll_no = request.roll_no
        timestamp = request.lamport_timestamp
        resource_id = self._get_resource_id(roll_no)
        
        # Update logical clock
        current_clock = self._update_logical_clock(timestamp)
        
        logger.info(f"[CS RELEASE] {roll_no} releasing resource '{resource_id}' at timestamp {timestamp}")
        
        # Add to request history
        self.request_history.append({
            'type': 'release',
            'roll_no': roll_no,
            'resource_id': resource_id,
            'timestamp': timestamp,
            'received_at': time.time()
        })
        
        with self.queue_lock:
            # Verify current holder
            if resource_id not in self.critical_sections:
                logger.warning(f"[CS RELEASE] Resource '{resource_id}' not held by anyone")
                return pb2.ReleaseCSResponse(success=False)
            
            current_holder = self.critical_sections[resource_id]['holder']
            if current_holder != roll_no:
                logger.warning(f"[CS RELEASE] {roll_no} trying to release resource '{resource_id}' held by {current_holder}")
                return pb2.ReleaseCSResponse(success=False)
            
            # Calculate holding time
            held_duration = time.time() - self.critical_sections[resource_id]['granted_at']
            logger.info(f"[CS RELEASE] Resource '{resource_id}' held for {held_duration:.2f} seconds")
            
            # Release the resource
            del self.critical_sections[resource_id]
            
            # Grant to next waiting process
            next_granted = self._grant_to_next_waiter(resource_id, current_clock)
            
            if next_granted:
                logger.info(f"[CS RELEASE] Granted resource '{resource_id}' to next waiter: {next_granted}")
            else:
                logger.info(f"[CS RELEASE] No waiters for resource '{resource_id}', resource is free")
        
        return pb2.ReleaseCSResponse(success=True)
    
    def _grant_to_next_waiter(self, resource_id: str, current_clock: int) -> Optional[str]:
        """Grant resource to next waiting process"""
        # Find next request for this resource
        next_request = None
        next_index = -1
        
        for i, (timestamp, roll_no, req_resource_id, queued_at) in enumerate(self.request_queue):
            if req_resource_id == resource_id:
                next_request = (timestamp, roll_no, req_resource_id, queued_at)
                next_index = i
                break
        
        if not next_request:
            return None
        
        timestamp, roll_no, _, queued_at = next_request
        
        # Grant critical section
        self.critical_sections[resource_id] = {
            'holder': roll_no,
            'timestamp': timestamp,
            'granted_at': time.time(),
            'clock': current_clock,
            'wait_time': time.time() - queued_at
        }
        
        # Remove from queue
        del list(self.request_queue)[next_index]
        self.request_queue = deque([
            req for i, req in enumerate(self.request_queue) if i != next_index
        ])
        
        # Notify waiting process
        if roll_no in self.waiting_processes:
            event = self.waiting_processes[roll_no]
            del self.waiting_processes[roll_no]
            
            # Set event to wake up waiting coroutine
            asyncio.create_task(self._notify_waiter(event))
        
        return roll_no
    
    async def _notify_waiter(self, event: asyncio.Event):
        """Notify a waiting process (async helper)"""
        event.set()
    
    def get_system_status(self) -> dict:
        """Get current system status for debugging"""
        with self.queue_lock, self.cs_lock:
            return {
                'logical_clock': self.logical_clock,
                'active_critical_sections': len(self.critical_sections),
                'waiting_requests': len(self.request_queue),
                'waiting_processes': len(self.waiting_processes),
                'critical_sections': {
                    resource_id: {
                        'holder': info['holder'],
                        'held_for': time.time() - info['granted_at'],
                        'timestamp': info['timestamp']
                    }
                    for resource_id, info in self.critical_sections.items()
                },
                'queue': [
                    {
                        'timestamp': ts,
                        'roll_no': roll_no,
                        'resource_id': resource_id,
                        'wait_time': time.time() - queued_at
                    }
                    for ts, roll_no, resource_id, queued_at in list(self.request_queue)[:10]  # Show first 10
                ],
                'recent_requests': list(self.request_history)[-20:]  # Show last 20
            }

# Additional service for system monitoring (optional)
class MonitoringServiceServicer:
    """Optional monitoring service for debugging and metrics"""
    
    def __init__(self, ra_service: RicartAgrawalaServiceServicer):
        self.ra_service = ra_service
    
    def get_status(self):
        """Get detailed system status"""
        return self.ra_service.get_system_status()

async def serve():
    """Start the Ricart-Agrawala Service"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    
    ra_service = RicartAgrawalaServiceServicer()
    pb2_grpc.add_RicartAgrawalaServiceServicer_to_server(ra_service, server)
    
    # Optional: Add monitoring service
    monitoring_service = MonitoringServiceServicer(ra_service)
    
    listen_addr = f'[::]:{RICART_AGRAWALA_PORT}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting Ricart-Agrawala Service on {listen_addr}")
    logger.info("Service supports distributed mutual exclusion for:")
    logger.info("  - Student data consistency operations")
    logger.info("  - Teacher mark update operations")
    logger.info("  - Global read operations")
    logger.info("  - Write transactions")
    
    await server.start()
    
    # Periodic status logging
    async def log_status():
        while True:
            await asyncio.sleep(60)  # Every minute
            status = ra_service.get_system_status()
            if status['active_critical_sections'] > 0 or status['waiting_requests'] > 0:
                logger.info(f"[STATUS] Active CS: {status['active_critical_sections']}, "
                          f"Waiting: {status['waiting_requests']}, "
                          f"Clock: {status['logical_clock']}")
    
    status_task = asyncio.create_task(log_status())
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Ricart-Agrawala Service...")
        status_task.cancel()
        await server.stop(5)

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nRicart-Agrawala Service stopped.") 