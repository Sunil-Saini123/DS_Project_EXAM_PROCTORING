#!/usr/bin/env python3
"""
Load Balancer Testing Script
Tests the load balancer functionality with multiple concurrent requests
"""

import asyncio
import grpc
import time
import random
import concurrent.futures
from typing import List
import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

MAIN_SERVER_URL = 'localhost:50050'
LOAD_BALANCER_URL = 'localhost:50055'

class LoadBalancerTester:
    def __init__(self):
        self.test_results = []
        self.concurrent_users = 0
        self.max_concurrent_reached = 0
    
    async def simulate_student_submission(self, student_id: int, session_id: str = "test_session"):
        """Simulate a student exam submission"""
        roll_no = f"TEST_STUDENT_{student_id:03d}"
        
        try:
            self.concurrent_users += 1
            self.max_concurrent_reached = max(self.max_concurrent_reached, self.concurrent_users)
            
            # Create sample answers
            answers = []
            for i in range(1, 11):  # 10 questions
                answers.append(pb2.Answer(
                    question_id=f"Q{i}",
                    selected_option=random.choice(["A", "B", "C"])
                ))
            
            # Create submission request
            submission = pb2.SubmitExamRequest(
                roll_no=roll_no,
                session_id=session_id,
                answers=answers,
                submit_type="manual",
                priority=0
            )
            
            # Send to load balancer
            start_time = time.time()
            
            channel = grpc.aio.insecure_channel(LOAD_BALANCER_URL)
            stub = pb2_grpc.LoadBalancerServiceStub(channel)
            
            response = await stub.RouteSubmission(
                pb2.RouteSubmissionRequest(
                    submission=submission,
                    current_load=self.concurrent_users
                )
            )
            
            await channel.close()
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            result = {
                'student_id': student_id,
                'roll_no': roll_no,
                'routed_to_backup': response.routed_to_backup,
                'success': response.result.success,
                'score': response.result.final_score,
                'processing_time': processing_time,
                'message': response.result.message
            }
            
            self.test_results.append(result)
            
            print(f"Student {roll_no}: {'BACKUP' if response.routed_to_backup else 'PRIMARY'} | "
                  f"Score: {response.result.final_score} | Time: {processing_time:.2f}s | "
                  f"Success: {response.result.success}")
            
            return result
            
        except Exception as e:
            print(f"Error with student {roll_no}: {e}")
            return None
        finally:
            self.concurrent_users -= 1
    
    async def test_load_balancer_threshold(self):
        """Test if load balancer correctly routes to backup when threshold is exceeded"""
        print("=== Testing Load Balancer Threshold ===")
        print(f"Sending 20 concurrent requests to test load balancing...")
        
        # Create 20 concurrent submission tasks
        tasks = []
        for i in range(1, 21):
            task = asyncio.create_task(
                self.simulate_student_submission(i, "load_test_session")
            )
            tasks.append(task)
            
            # Add small delay to simulate realistic submission timing
            await asyncio.sleep(0.1)
        
        # Wait for all submissions to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if r and isinstance(r, dict)]
        primary_count = sum(1 for r in successful_results if not r['routed_to_backup'])
        backup_count = sum(1 for r in successful_results if r['routed_to_backup'])
        
        print(f"\n=== Load Balancing Results ===")
        print(f"Total submissions: {len(successful_results)}")
        print(f"Processed by PRIMARY server: {primary_count}")
        print(f"Processed by BACKUP server: {backup_count}")
        print(f"Max concurrent users reached: {self.max_concurrent_reached}")
        
        avg_time = sum(r['processing_time'] for r in successful_results) / len(successful_results)
        print(f"Average processing time: {avg_time:.2f} seconds")
        
        if backup_count > 0:
            print("✅ Load balancer is working - requests routed to backup server!")
        else:
            print("⚠️  No requests routed to backup - load may not have exceeded threshold")
    
    async def test_backup_server_health(self):
        """Test backup server health check"""
        print("\n=== Testing Backup Server Health ===")
        
        try:
            channel = grpc.aio.insecure_channel(LOAD_BALANCER_URL)
            stub = pb2_grpc.LoadBalancerServiceStub(channel)
            
            response = await stub.GetServerStatus(
                pb2.GetServerStatusRequest()
            )
            
            await channel.close()
            
            print(f"Main server healthy: {response.main_server_healthy}")
            print(f"Backup server healthy: {response.backup_server_healthy}")
            print(f"Current load: {response.current_load}")
            print(f"Max capacity: {response.max_capacity}")
            
            if response.backup_server_healthy:
                print("✅ Backup server is healthy and available")
            else:
                print("❌ Backup server is not available")
                
        except Exception as e:
            print(f"❌ Error checking server status: {e}")
    
    async def test_gradual_load_increase(self):
        """Test gradual load increase to observe load balancing behavior"""
        print("\n=== Testing Gradual Load Increase ===")
        
        # Send requests in batches with increasing size
        batch_sizes = [2, 5, 8, 12, 18, 25]
        
        for batch_size in batch_sizes:
            print(f"\nSending batch of {batch_size} requests...")
            
            tasks = []
            batch_start_id = len(self.test_results) + 1
            
            for i in range(batch_size):
                task = asyncio.create_task(
                    self.simulate_student_submission(
                        batch_start_id + i, 
                        f"batch_test_{batch_size}"
                    )
                )
                tasks.append(task)
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_batch = [r for r in batch_results if r and isinstance(r, dict)]
            
            primary_in_batch = sum(1 for r in successful_batch if not r['routed_to_backup'])
            backup_in_batch = sum(1 for r in successful_batch if r['routed_to_backup'])
            
            print(f"  Batch {batch_size}: PRIMARY={primary_in_batch}, BACKUP={backup_in_batch}")
            
            # Small delay between batches
            await asyncio.sleep(2)
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*60)
        print("LOAD BALANCER TEST REPORT")
        print("="*60)
        
        if not self.test_results:
            print("No test results to report")
            return
        
        total_requests = len(self.test_results)
        successful_requests = sum(1 for r in self.test_results if r['success'])
        primary_requests = sum(1 for r in self.test_results if not r['routed_to_backup'])
        backup_requests = sum(1 for r in self.test_results if r['routed_to_backup'])
        
        avg_processing_time = sum(r['processing_time'] for r in self.test_results) / total_requests
        avg_score = sum(r['score'] for r in self.test_results if r['success']) / successful_requests
        
        print(f"Total Requests Sent: {total_requests}")
        print(f"Successful Requests: {successful_requests} ({(successful_requests/total_requests)*100:.1f}%)")
        print(f"Failed Requests: {total_requests - successful_requests}")
        print(f"\nLoad Distribution:")
        print(f"  PRIMARY server: {primary_requests} ({(primary_requests/total_requests)*100:.1f}%)")
        print(f"  BACKUP server: {backup_requests} ({(backup_requests/total_requests)*100:.1f}%)")
        print(f"\nPerformance Metrics:")
        print(f"  Average processing time: {avg_processing_time:.2f} seconds")
        print(f"  Average exam score: {avg_score:.1f}/100")
        print(f"  Max concurrent users: {self.max_concurrent_reached}")
        
        # Performance analysis
        if backup_requests > 0:
            primary_times = [r['processing_time'] for r in self.test_results if not r['routed_to_backup']]
            backup_times = [r['processing_time'] for r in self.test_results if r['routed_to_backup']]
            
            if primary_times and backup_times:
                avg_primary_time = sum(primary_times) / len(primary_times)
                avg_backup_time = sum(backup_times) / len(backup_times)
                
                print(f"\nServer Performance Comparison:")
                print(f"  PRIMARY server avg time: {avg_primary_time:.2f}s")
                print(f"  BACKUP server avg time: {avg_backup_time:.2f}s")
        
        print(f"\nLoad Balancer Status: {'✅ WORKING' if backup_requests > 0 else '⚠️ NOT TRIGGERED'}")
        
        if backup_requests == 0:
            print("  - No requests were routed to backup server")
            print("  - Try increasing concurrent load or reducing MAX_PRIMARY_LOAD")
        
        print("="*60)

async def main():
    """Main testing function"""
    tester = LoadBalancerTester()
    
    print("Load Balancer Testing Tool")
    print("Make sure all services are running:")
    print("1. Ricart-Agrawala Service (port 50052)")
    print("2. Consistency Service (port 50053)")  
    print("3. Load Balancer Service (port 50055)")
    print("4. Main Server (port 50050)")
    print("\nStarting tests in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    # Run all tests
    await tester.test_backup_server_health()
    await tester.test_gradual_load_increase()
    await tester.test_load_balancer_threshold()
    
    # Generate final report
    tester.generate_report()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
    except Exception as e:
        print(f"Testing failed: {e}")