#!/usr/bin/env python3
"""
Consistency Service - Manages data consistency and replication across the distributed system
Handles read/write operations with proper locking and data sharding
"""

import asyncio
import grpc
import json
import os
import logging
import threading
import time
import hashlib
from concurrent import futures
from typing import Dict, List, Optional, Any

import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

# Configuration
CONSISTENCY_SERVICE_PORT = 50053
RICART_AGRAWALA_URL = 'localhost:50052'
DATA_DIR = "exam_data"
BACKUP_DATA_DIR = "exam_data_backup"
NUM_SHARDS = 4

# Global state
student_data_cache: Dict[str, pb2.Student] = {}
active_transactions: Dict[str, Dict[str, Any]] = {}
shard_locks: Dict[int, threading.RLock] = {}

# Initialize shard locks
for i in range(NUM_SHARDS):
    shard_locks[i] = threading.RLock()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ConsistencyService')

# Sample student data for initialization
INITIAL_STUDENT_DATA = {
    "23102A0027": {"name": "RIYA SACHIN GAIKWAD", "ISA": 34, "MSE": 11, "ESE": 35},
    "23102A0028": {"name": "RUTUJA DINESH KAMALE", "ISA": 36, "MSE": 13, "ESE": 31},
    "23102A0029": {"name": "MAYURESH KRISHNAKANT SAWANT", "ISA": 39, "MSE": 19, "ESE": 22},
    "23102A0031": {"name": "KRISH RAINA", "ISA": 17, "MSE": 8, "ESE": 0},
    "23102A0032": {"name": "ASHA SANJAY BHOKARE", "ISA": 33, "MSE": 15, "ESE": 32},
    "23102A0033": {"name": "VICKY VILAS PUKALE", "ISA": 30, "MSE": 11, "ESE": 39},
    "23102A0034": {"name": "KAVYA MILIND TELAVANE", "ISA": 39, "MSE": 15, "ESE": 26},
    "23102A0035": {"name": "ESHA DINESH PAWAR", "ISA": 36, "MSE": 18, "ESE": 26},
    "23102A0036": {"name": "SUNIL ROSHANLAL SAINI", "ISA": 38, "MSE": 9, "ESE": 33},
    "23102A0037": {"name": "YASHIKA VIJAY DHAWRAL", "ISA": 35, "MSE": 17, "ESE": 28},
    "23102A0038": {"name": "PRAPTI VIVEK DETHE", "ISA": 38, "MSE": 17, "ESE": 25},
    "23102A0039": {"name": "MUBINA SYED HASAN", "ISA": 39, "MSE": 16, "ESE": 25},
    "23102A0040": {"name": "AYUSH AMIT MANORE", "ISA": 34, "MSE": 9, "ESE": 37},
    "23102A0041": {"name": "HARSHAL SURESH PATIL", "ISA": 35, "MSE": 9, "ESE": 36},
    "23102A0042": {"name": "AASHNA PRASHANT GAIKWAD", "ISA": 33, "MSE": 7, "ESE": 40},
    "23102A0043": {"name": "GHANSHYAM JETHARAM KUMAVAT", "ISA": 15, "MSE": 7, "ESE": 0},
    "23102A0044": {"name": "RUSHIKESH RAMESH AMBERKAR", "ISA": 38, "MSE": 7, "ESE": 35},
    "23102A0045": {"name": "SHRUTI ANIL DUBEY", "ISA": 33, "MSE": 9, "ESE": 38}
}

def ensure_data_directories():
    """Ensure data directories exist"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DATA_DIR, exist_ok=True)

def get_shard_id(roll_no: str) -> int:
    """Determine shard ID for a roll number using consistent hashing"""
    hash_object = hashlib.md5(roll_no.encode())
    hash_hex = hash_object.hexdigest()
    return int(hash_hex, 16) % NUM_SHARDS

def get_shard_file_path(shard_id: int, is_backup: bool = False) -> str:
    """Get file path for a specific shard"""
    base_dir = BACKUP_DATA_DIR if is_backup else DATA_DIR
    return os.path.join(base_dir, f"shard_{shard_id}.json")

def load_shard_data(shard_id: int) -> Dict[str, Any]:
    """Load data from a shard file"""
    file_path = get_shard_file_path(shard_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading shard {shard_id}: {e}")
            return {}
    return {}

def save_shard_data(shard_id: int, data: Dict[str, Any], is_backup: bool = False):
    """Save data to a shard file"""
    file_path = get_shard_file_path(shard_id, is_backup)
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving shard {shard_id}: {e}")

def initialize_data():
    """Initialize shard data with sample student data"""
    ensure_data_directories()
    
    # Distribute initial data across shards
    shard_data: Dict[int, Dict[str, Any]] = {i: {} for i in range(NUM_SHARDS)}
    
    for roll_no, data in INITIAL_STUDENT_DATA.items():
        shard_id = get_shard_id(roll_no)
        shard_data[shard_id][roll_no] = {
            "roll_no": roll_no,
            "name": data["name"],
            "isa_marks": data["ISA"],
            "mse_marks": data["MSE"],
            "ese_marks": data["ESE"],
            "status": "registered",
            "cheating_count": 0
        }
    
    # Save to files
    for shard_id, data in shard_data.items():
        if data:  # Only save non-empty shards
            save_shard_data(shard_id, data)
            save_shard_data(shard_id, data, is_backup=True)
    
    logger.info(f"Initialized {len(INITIAL_STUDENT_DATA)} students across {NUM_SHARDS} shards")

def load_all_student_data() -> Dict[str, pb2.Student]:
    """Load all student data from shards into memory cache"""
    all_students = {}
    
    for shard_id in range(NUM_SHARDS):
        shard_data = load_shard_data(shard_id)
        for roll_no, data in shard_data.items():
            student = pb2.Student(
                roll_no=data["roll_no"],
                name=data["name"],
                isa_marks=data.get("isa_marks", 0),
                mse_marks=data.get("mse_marks", 0),
                ese_marks=data.get("ese_marks", 0),
                status=data.get("status", "registered"),
                cheating_count=data.get("cheating_count", 0)
            )
            all_students[roll_no] = student
    
    return all_students

class ConsistencyServiceServicer(pb2_grpc.ConsistencyServiceServicer):
    def __init__(self):
        self.transaction_counter = 0
        self.transaction_lock = threading.Lock()
        
        # Load initial data
        global student_data_cache
        student_data_cache = load_all_student_data()
        logger.info(f"Loaded {len(student_data_cache)} students into cache")
    
    async def ReadStudentData(self, request, context):
        """Read student data with consistency guarantees"""
        roll_no = request.roll_no
        requester_type = request.requester_type
        
        shard_id = get_shard_id(roll_no)
        
        # Check cache first
        if roll_no in student_data_cache:
            logger.info(f"Read student {roll_no} from cache for {requester_type}")
            return pb2.ReadStudentDataResponse(
                success=True,
                student=student_data_cache[roll_no],
                message="Data retrieved successfully",
                chunk_id=shard_id
            )
        
        # If not in cache, try to read from disk
        with shard_locks[shard_id]:
            shard_data = load_shard_data(shard_id)
            if roll_no in shard_data:
                data = shard_data[roll_no]
                student = pb2.Student(
                    roll_no=data["roll_no"],
                    name=data["name"],
                    isa_marks=data.get("isa_marks", 0),
                    mse_marks=data.get("mse_marks", 0),
                    ese_marks=data.get("ese_marks", 0),
                    status=data.get("status", "registered"),
                    cheating_count=data.get("cheating_count", 0)
                )
                
                # Update cache
                student_data_cache[roll_no] = student
                
                logger.info(f"Read student {roll_no} from disk for {requester_type}")
                return pb2.ReadStudentDataResponse(
                    success=True,
                    student=student,
                    message="Data retrieved successfully",
                    chunk_id=shard_id
                )
        
        # Student not found
        return pb2.ReadStudentDataResponse(
            success=False,
            student=pb2.Student(),
            message="Student not found",
            chunk_id=shard_id
        )
    
    async def WriteStudentData(self, request, context):
        """Write student data with consistency guarantees"""
        roll_no = request.roll_no
        student_data = request.student_data
        requester_type = request.requester_type
        
        shard_id = get_shard_id(roll_no)
        
        # Use Ricart-Agrawala for distributed locking if requester is teacher
        cs_acquired = False
        channel_ra = None
        stub_ra = None
        
        if requester_type == "teacher":
            try:
                channel_ra = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
                stub_ra = pb2_grpc.RicartAgrawalaServiceStub(channel_ra)
                
                cs_response = await stub_ra.RequestCS(
                    pb2.RequestCSRequest(
                        roll_no=f"consistency_{roll_no}",
                        lamport_timestamp=int(time.time() * 1000000)
                    )
                )
                
                cs_acquired = cs_response.success
                if not cs_acquired:
                    await channel_ra.close()
                    return pb2.WriteStudentDataResponse(
                        success=False,
                        message="Could not acquire distributed lock",
                        updated_student=pb2.Student()
                    )
                    
            except grpc.RpcError as e:
                logger.error(f"Failed to acquire distributed lock: {e}")
                if channel_ra:
                    await channel_ra.close()
                return pb2.WriteStudentDataResponse(
                    success=False,
                    message="Lock acquisition failed",
                    updated_student=pb2.Student()
                )
        
        try:
            # Acquire local shard lock
            with shard_locks[shard_id]:
                # Load current shard data
                shard_data = load_shard_data(shard_id)
                
                # Update student data
                student_dict = {
                    "roll_no": student_data.roll_no,
                    "name": student_data.name,
                    "isa_marks": student_data.isa_marks,
                    "mse_marks": student_data.mse_marks,
                    "ese_marks": student_data.ese_marks,
                    "status": student_data.status,
                    "cheating_count": student_data.cheating_count
                }
                
                shard_data[roll_no] = student_dict
                
                # Save to primary and backup
                save_shard_data(shard_id, shard_data)
                save_shard_data(shard_id, shard_data, is_backup=True)
                
                # Update cache
                student_data_cache[roll_no] = pb2.Student(**student_dict)
                
                logger.info(f"Updated student {roll_no} by {requester_type}")
                
                return pb2.WriteStudentDataResponse(
                    success=True,
                    message="Data updated successfully",
                    updated_student=student_data_cache[roll_no]
                )
        
        finally:
            # Release distributed lock if acquired
            if cs_acquired and stub_ra:
                try:
                    await stub_ra.ReleaseCS(
                        pb2.ReleaseCSRequest(
                            roll_no=f"consistency_{roll_no}",
                            lamport_timestamp=int(time.time() * 1000000)
                        )
                    )
                except grpc.RpcError as e:
                    logger.error(f"Failed to release distributed lock: {e}")
                
                if channel_ra:
                    await channel_ra.close()
    
    async def BeginReadTransaction(self, request, context):
        """Begin a read transaction for consistent data access"""
        roll_no = request.roll_no
        transaction_id = request.transaction_id
        
        with self.transaction_lock:
            if transaction_id in active_transactions:
                return pb2.BeginReadTransactionResponse(
                    success=False,
                    message="Transaction already active",
                    student=pb2.Student()
                )
            
            # Create transaction record
            active_transactions[transaction_id] = {
                'type': 'read',
                'roll_no': roll_no,
                'start_time': time.time(),
                'shard_id': get_shard_id(roll_no)
            }
        
        # Read student data
        read_response = await self.ReadStudentData(
            pb2.ReadStudentDataRequest(
                roll_no=roll_no,
                requester_type="transaction"
            ), context
        )
        
        if read_response.success:
            return pb2.BeginReadTransactionResponse(
                success=True,
                message="Read transaction started",
                student=read_response.student
            )
        else:
            # Clean up failed transaction
            with self.transaction_lock:
                active_transactions.pop(transaction_id, None)
            
            return pb2.BeginReadTransactionResponse(
                success=False,
                message=read_response.message,
                student=pb2.Student()
            )
    
    async def EndReadTransaction(self, request, context):
        """End a read transaction"""
        transaction_id = request.transaction_id
        
        with self.transaction_lock:
            if transaction_id not in active_transactions:
                return pb2.EndReadTransactionResponse(success=False)
            
            del active_transactions[transaction_id]
        
        return pb2.EndReadTransactionResponse(success=True)
    
    async def BeginWriteTransaction(self, request, context):
        """Begin a write transaction with distributed locking"""
        roll_no = request.roll_no
        transaction_id = request.transaction_id
        
        with self.transaction_lock:
            if transaction_id in active_transactions:
                return pb2.BeginWriteTransactionResponse(
                    success=False,
                    message="Transaction already active",
                    current_student=pb2.Student()
                )
            
            # Create transaction record
            active_transactions[transaction_id] = {
                'type': 'write',
                'roll_no': roll_no,
                'start_time': time.time(),
                'shard_id': get_shard_id(roll_no)
            }
        
        # Acquire distributed lock
        try:
            channel = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
            stub = pb2_grpc.RicartAgrawalaServiceStub(channel)
            
            cs_response = await stub.RequestCS(
                pb2.RequestCSRequest(
                    roll_no=f"write_tx_{roll_no}",
                    lamport_timestamp=int(time.time() * 1000000)
                )
            )
            
            await channel.close()
            
            if not cs_response.success:
                with self.transaction_lock:
                    del active_transactions[transaction_id]
                
                return pb2.BeginWriteTransactionResponse(
                    success=False,
                    message="Could not acquire distributed lock",
                    current_student=pb2.Student()
                )
            
            # Store lock info in transaction
            active_transactions[transaction_id]['lock_acquired'] = True
            
        except grpc.RpcError as e:
            logger.error(f"Failed to acquire write lock: {e}")
            with self.transaction_lock:
                del active_transactions[transaction_id]
            
            return pb2.BeginWriteTransactionResponse(
                success=False,
                message="Lock acquisition failed",
                current_student=pb2.Student()
            )
        
        # Read current data
        read_response = await self.ReadStudentData(
            pb2.ReadStudentDataRequest(
                roll_no=roll_no,
                requester_type="transaction"
            ), context
        )
        
        if read_response.success:
            return pb2.BeginWriteTransactionResponse(
                success=True,
                message="Write transaction started",
                current_student=read_response.student
            )
        else:
            # Clean up failed transaction and release lock
            await self._cleanup_write_transaction(transaction_id)
            
            return pb2.BeginWriteTransactionResponse(
                success=False,
                message=read_response.message,
                current_student=pb2.Student()
            )
    
    async def EndWriteTransaction(self, request, context):
        """End a write transaction with data commit"""
        roll_no = request.roll_no
        transaction_id = request.transaction_id
        updated_student = request.updated_student
        
        if transaction_id not in active_transactions:
            return pb2.EndWriteTransactionResponse(
                success=False,
                final_student=pb2.Student()
            )
        
        # Write the updated data
        write_response = await self.WriteStudentData(
            pb2.WriteStudentDataRequest(
                roll_no=roll_no,
                student_data=updated_student,
                requester_type="transaction"
            ), context
        )
        
        # Clean up transaction and release lock
        await self._cleanup_write_transaction(transaction_id)
        
        if write_response.success:
            return pb2.EndWriteTransactionResponse(
                success=True,
                final_student=write_response.updated_student
            )
        else:
            return pb2.EndWriteTransactionResponse(
                success=False,
                final_student=pb2.Student()
            )
    
    async def GetAllStudentsData(self, request, context):
        """Get data for all students"""
        requester_type = request.requester_type
        
        # If teacher is requesting, use distributed locking for consistency
        if requester_type == "teacher":
            try:
                channel = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
                stub = pb2_grpc.RicartAgrawalaServiceStub(channel)
                
                # Acquire global read lock
                cs_response = await stub.RequestCS(
                    pb2.RequestCSRequest(
                        roll_no="global_read_all",
                        lamport_timestamp=int(time.time() * 1000000)
                    )
                )
                
                if cs_response.success:
                    try:
                        # Refresh cache from disk to ensure consistency
                        fresh_data = load_all_student_data()
                        student_data_cache.update(fresh_data)
                        
                        students_list = list(student_data_cache.values())
                        logger.info(f"Retrieved {len(students_list)} students for {requester_type}")
                        
                        return pb2.GetAllStudentsDataResponse(
                            success=True,
                            students=students_list,
                            message="Data retrieved successfully"
                        )
                    
                    finally:
                        # Release global read lock
                        await stub.ReleaseCS(
                            pb2.ReleaseCSRequest(
                                roll_no="global_read_all",
                                lamport_timestamp=int(time.time() * 1000000)
                            )
                        )
                
                await channel.close()
                
            except grpc.RpcError as e:
                logger.error(f"Failed to acquire global read lock: {e}")
                if channel:
                    await channel.close()
                
                # Fallback to cache data
                students_list = list(student_data_cache.values())
                return pb2.GetAllStudentsDataResponse(
                    success=True,
                    students=students_list,
                    message="Data retrieved from cache (lock failed)"
                )
        
        # For non-teacher requests, just return cache data
        students_list = list(student_data_cache.values())
        logger.info(f"Retrieved {len(students_list)} students from cache for {requester_type}")
        
        return pb2.GetAllStudentsDataResponse(
            success=True,
            students=students_list,
            message="Data retrieved successfully"
        )
    
    async def _cleanup_write_transaction(self, transaction_id: str):
        """Clean up a write transaction and release distributed locks"""
        transaction = active_transactions.get(transaction_id)
        if not transaction:
            return
        
        # Release distributed lock if acquired
        if transaction.get('lock_acquired'):
            try:
                channel = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
                stub = pb2_grpc.RicartAgrawalaServiceStub(channel)
                
                await stub.ReleaseCS(
                    pb2.ReleaseCSRequest(
                        roll_no=f"write_tx_{transaction['roll_no']}",
                        lamport_timestamp=int(time.time() * 1000000)
                    )
                )
                
                await channel.close()
                
            except grpc.RpcError as e:
                logger.error(f"Failed to release write transaction lock: {e}")
        
        # Remove transaction record
        with self.transaction_lock:
            active_transactions.pop(transaction_id, None)

async def serve():
    """Start the Consistency Service"""
    # Initialize data on startup
    initialize_data()
    
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    
    consistency_service = ConsistencyServiceServicer()
    pb2_grpc.add_ConsistencyServiceServicer_to_server(consistency_service, server)
    
    listen_addr = f'[::]:{CONSISTENCY_SERVICE_PORT}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"Starting Consistency Service on {listen_addr}")
    
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Consistency Service...")
        await server.stop(5)

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nConsistency Service stopped.")