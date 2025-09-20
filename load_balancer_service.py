#!/usr/bin/env python3
"""
Load Balancer Service - Handles request distribution and failover
Routes submissions to primary or backup servers based on load
"""

import asyncio
import grpc
import logging
import time
import threading
from concurrent import futures
from typing import Dict, List, Optional, Deque
from collections import deque

import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

# Configuration
LOAD_BALANCER_PORT = 50055
BACKUP_SERVER_PORT = 50056
MAX_PRIMARY_LOAD = 15  # Maximum concurrent requests for primary server
HEALTH_CHECK_INTERVAL = 30  # seconds

# Global state
current_load = 0
load_lock = threading.Lock()
request_queue: Deque = deque()
processed_submissions = 0
backup_server_available = False

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('LoadBalancer')

class LoadBalancerServiceServicer(pb2_grpc.LoadBalancerServiceServicer):
    def __init__(self):
        self.backup_health_check_task = None
        self.start_health_monitoring()
    
    def start_health_monitoring(self):
        """Start background health monitoring for backup server"""
        self.backup_health_check_task = asyncio.create_task(self._monitor_backup_health())
    
    async def RouteSubmission(self, request, context):
        """Route submission to primary or backup server based on load"""
        global current_load, processed_submissions
        
        submission = request.submission
        reported_load = request.current_load
        
        # Update current load
        with load_lock:
            current_load = max(current_load, reported_load)
        
        logger.info(f"Routing submission for {submission.roll_no}, current load: {current_load}")
        
        # Determine routing strategy
        should_use_backup = (current_load >= MAX_PRIMARY_LOAD) and backup_server_available
        
        if should_use_backup:
            logger.info(f"Routing {submission.roll_no} to backup server (load: {current_load})")
            result = await self._route_to_backup(submission)
        else:
            logger.info(f"Processing {submission.roll_no} on primary server")
            result = await self._process_on_primary(submission)
        
        # Update metrics
        with load_lock:
            processed_submissions += 1
            if current_load > 0:
                current_load -= 1
        
        return pb2.RouteSubmissionResponse(
            routed_to_backup=should_use_backup,
            result=result
        )
    
    async def GetServerStatus(self, request, context):
        """Get current server status and health"""
        return pb2.GetServerStatusResponse(
            main_server_healthy=True,  # Assume healthy if service is running
            backup_server_healthy=backup_server_available,
            current_load=current_load,
            max_capacity=MAX_PRIMARY_LOAD
        )
    
    async def MigrateRequests(self, request, context):
        """Migrate multiple requests to backup server"""
        requests = request.requests
        target_server = request.target_server
        
        logger.info(f"Migrating {len(requests)} requests to {target_server}")
        
        results = []
        for req in requests:
            if target_server == "backup":
                result = await self._route_to_backup(req)
            else:
                result = await self._process_on_primary(req)
            results.append(result)
        
        return pb2.MigrateRequestsResponse(
            success=True,
            results=results
        )
    
    async def _process_on_primary(self, submission: pb2.SubmitExamRequest) -> pb2.SubmitExamResponse:
        """Process submission on primary server (simulate processing)"""
        try:
            # Simulate processing time
            await asyncio.sleep(0.5)
            
            # Calculate score (simplified)
            score = len(submission.answers) * 10  # 10 points per answered question
            
            logger.info(f"Primary server processed {submission.roll_no}, score: {score}")
            
            return pb2.SubmitExamResponse(
                success=True,
                message=f"{submission.submit_type.capitalize()} submission processed successfully",
                final_score=score
            )
            
        except Exception as e:
            logger.error(f"Primary server processing failed for {submission.roll_no}: {e}")
            return pb2.SubmitExamResponse(
                success=False,
                message="Processing failed on primary server",
                final_score=0
            )
    
    async def _route_to_backup(self, submission: pb2.SubmitExamRequest) -> pb2.SubmitExamResponse:
        """Route submission to backup server"""
        try:
            channel = grpc.aio.insecure_channel(f'localhost:{BACKUP_SERVER_PORT}')
            stub = pb2_grpc.BackupServiceStub(channel)
            
            # Forward to backup server
            response = await stub.ProcessSubmission(
                pb2.ProcessSubmissionRequest(
                    submission=submission,
                    forwarded_from_primary=True
                )
            )
            
            await channel.close()
            
            logger.info(f"Backup server processed {submission.roll_no}")
            return response
            
        except grpc.RpcError as e:
            logger.error(f"Backup server processing failed for {submission.roll_no}: {e}")
            # Fallback to primary server processing
            return await self._process_on_primary(submission)
    
    async def _monitor_backup_health(self):
        """Monitor backup server health"""
        global backup_server_available
        
        while True:
            try:
                channel = grpc.aio.insecure_channel(f'localhost:{BACKUP_SERVER_PORT}')
                stub = pb2_grpc.BackupServiceStub(channel)
                
                # Send health check
                await stub.HealthCheck(pb2.HealthCheckRequest())
                
                await channel.close()
                
                if not backup_server_available:
                    logger.info("Backup server is now available")
                backup_server_available = True
                
            except grpc.RpcError:
                if backup_server_available:
                    logger.warning("Backup server is unavailable")
                backup_server_available = False
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# Backup Server Service Definition (would normally be separate)
class BackupServiceServicer(pb2_grpc.BackupServiceServicer):
    def __init__(self):
        self.processed_count = 0
    
    async def ProcessSubmission(self, request, context):
        """Process submission on backup server"""
        submission = request.submission
        forwarded = request.forwarded_from_primary
        
        try:
            # Simulate backup server processing (slower but reliable)
            await asyncio.sleep(2.0)  # Backup is slower
            
            # Calculate score
            score = len(submission.answers) * 10
            
            self.processed_count += 1
            logger.info(f"Backup server processed {submission.roll_no} (#{self.processed_count}), score: {score}")
            
            return pb2.SubmitExamResponse(
                success=True,
                message=f"Backup server: {submission.submit_type.capitalize()} submission processed",
                final_score=score
            )
            
        except Exception as e:
            logger.error(f"Backup server processing failed for {submission.roll_no}: {e}")
            return pb2.SubmitExamResponse(
                success=False,
                message="Processing failed on backup server",
                final_score=0
            )
    
    async def HealthCheck(self, request, context):
        """Health check endpoint"""
        return pb2.HealthCheckResponse(
            healthy=True,
            processed_requests=self.processed_count,
            load=0  # Backup server reports minimal load
        )

async def serve_load_balancer():
    """Start the Load Balancer Service"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    
    load_balancer = LoadBalancerServiceServicer()
    pb2_grpc.add_LoadBalancerServiceServicer_to_server(load_balancer, server)
    
    listen_addr = f'[::]:{LOAD_BALANCER_PORT}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting Load Balancer Service on {listen_addr}")
    
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Load Balancer Service...")
        if load_balancer.backup_health_check_task:
            load_balancer.backup_health_check_task.cancel()
        await server.stop(5)

async def serve_backup_server():
    """Start the Backup Server"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=5))
    
    backup_service = BackupServiceServicer()
    pb2_grpc.add_BackupServiceServicer_to_server(backup_service, server)
    
    listen_addr = f'[::]:{BACKUP_SERVER_PORT}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting Backup Server on {listen_addr}")
    
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Backup Server...")
        await server.stop(5)

async def main():
    """Run both load balancer and backup server"""
    # Run both services concurrently
    await asyncio.gather(
        serve_load_balancer(),
        serve_backup_server()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLoad Balancer and Backup Server stopped.")