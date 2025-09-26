#!/usr/bin/env python3
"""
Fixed Main Server - Proper cheating detection and data clearing
"""

import asyncio
import grpc
import time
import uuid
import logging
import threading
import random
import pandas as pd
import os
from concurrent import futures
from typing import Dict, List, Optional
import json
from datetime import datetime

# Generated protobuf imports
import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

# Configuration
MAIN_SERVER_PORT = 50050
CONSISTENCY_SERVICE_URL = 'localhost:50053'
RICART_AGRAWALA_URL = 'localhost:50052'
TIME_SERVICE_URL = 'localhost:50054'
LOAD_BALANCER_URL = 'localhost:50055'

# Global state
exam_sessions: Dict[str, dict] = {}
active_students: Dict[str, dict] = {}
completed_students: Dict[str, dict] = {}  
exam_results: Dict[str, dict] = {}  
current_session_id: Optional[str] = None  
system_logs: List[str] = []  # Store system logs
cheating_offenses: Dict[str, int] = {}  # Track cheating offenses per student

# FIXED: Add cheating monitoring control
cheating_monitor_active = False
cheating_monitor_task = None

exam_questions = [
    pb2.Question(
        question_id="Q1", 
        text="What is the primary goal of a distributed system?", 
        options=["A. Transparency", "B. Centralization", "C. Data redundancy"],
        correct_answer="A"
    ),
    pb2.Question(
        question_id="Q2", 
        text="In a client-server architecture, which entity initiates the communication?", 
        options=["A. The server", "B. Both client and server", "C. The client"],
        correct_answer="C"
    ),
    pb2.Question(
        question_id="Q3", 
        text="Which consistency model is the most restrictive?", 
        options=["A. Weak consistency", "B. Strict consistency", "C. Eventual consistency"],
        correct_answer="B"
    ),
    pb2.Question(
        question_id="Q4", 
        text="What is a 'deadlock' in a distributed system?", 
        options=["A. Node failure", "B. Processes blocked waiting for each other", "C. Network partition"],
        correct_answer="B"
    ),
    pb2.Question(
        question_id="Q5", 
        text="What is Lamport's algorithm used for?", 
        options=["A. Network routing", "B. Data encryption", "C. Logical clock synchronization"],
        correct_answer="C"
    ),
    pb2.Question(
        question_id="Q6", 
        text="Which is an example of a distributed file system?", 
        options=["A. Google File System (GFS)", "B. Ext4", "C. NTFS"],
        correct_answer="A"
    ),
    pb2.Question(
        question_id="Q7", 
        text="What is a 'race condition'?", 
        options=["A. Multiple processes accessing shared data simultaneously", "B. System out of memory", "C. Incorrect server response"],
        correct_answer="A"
    ),
    pb2.Question(
        question_id="Q8", 
        text="Which model treats all nodes as equals?", 
        options=["A. Client-server", "B. Peer-to-peer", "C. Cloud computing"],
        correct_answer="B"
    ),
    pb2.Question(
        question_id="Q9", 
        text="What is the CAP theorem?", 
        options=["A. Consistency, Availability, Partition Tolerance", "B. Concurrency, Atomicity, Performance", "C. Client, Architecture, Protocol"],
        correct_answer="A"
    ),
    pb2.Question(
        question_id="Q10", 
        text="What is 'transparency' in distributed systems?", 
        options=["A. Easy to debug", "B. Data always visible", "C. Concealing distributed nature from user"],
        correct_answer="C"
    )
]

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MainServer')

def add_system_log(message: str):
    """Add a log message to system logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] MainServer: {message}"
    system_logs.append(log_entry)
    logger.info(message)
    
    # Keep only last 1000 logs
    if len(system_logs) > 1000:
        system_logs[:] = system_logs[-1000:]

# FIXED: Global cheating detection function
async def start_cheating_detection_system():
    """FIXED: Enhanced cheating detection system that actually works"""
    global cheating_monitor_active, cheating_monitor_task
    
    if cheating_monitor_task and not cheating_monitor_task.done():
        add_system_log("Cheating detection system already running")
        return
    
    cheating_monitor_active = True
    add_system_log("🚨 STARTING ENHANCED CHEATING DETECTION SYSTEM")
    
    async def cheating_monitor():
        detection_cycles = 0
        while cheating_monitor_active:
            try:
                detection_cycles += 1
                
                # Get currently active students
                current_active = [
                    roll_no for roll_no, data in active_students.items() 
                    if data.get('status') == 'active'
                ]
                
                if not current_active:
                    await asyncio.sleep(15)  # Check every 15 seconds when no students
                    continue
                
                add_system_log(f"🔍 Cheating detection cycle #{detection_cycles}: monitoring {len(current_active)} active students")
                
                # 20% chance per cycle (more aggressive detection)
                if random.randint(1, 100) <= 70:
                    # Pick a random active student to "catch"
                    caught_student = random.choice(current_active)
                    await handle_cheating_detected(caught_student)
                    
                    # Small delay after detection to make it more realistic
                    await asyncio.sleep(5)
                
                # Wait 12 seconds between checks (faster detection)
                await asyncio.sleep(20)
                
            except Exception as e:
                add_system_log(f"❌ Error in cheating detection system: {e}")
                await asyncio.sleep(20)
    
    cheating_monitor_task = asyncio.create_task(cheating_monitor())

async def stop_cheating_detection_system():
    """Stop the cheating detection system"""
    global cheating_monitor_active, cheating_monitor_task
    
    cheating_monitor_active = False
    if cheating_monitor_task and not cheating_monitor_task.done():
        cheating_monitor_task.cancel()
        try:
            await cheating_monitor_task
        except asyncio.CancelledError:
            pass
    
    add_system_log("🛑 STOPPED CHEATING DETECTION SYSTEM")

async def handle_cheating_detected(roll_no: str):
    """FIXED: Handle detected cheating incident with proper updates"""
    try:
        # Increment cheating count
        cheating_offenses[roll_no] = cheating_offenses.get(roll_no, 0) + 1
        current_count = cheating_offenses[roll_no]
        
        add_system_log(f"🚨 CHEATING DETECTED: Student {roll_no} caught cheating! (Offense #{current_count})")
        
        # Update consistency service
        channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
        stub = pb2_grpc.ConsistencyServiceStub(channel)

        # Read current student data
        read_response = await stub.ReadStudentData(
            pb2.ReadStudentDataRequest(
                roll_no=roll_no,
                requester_type="system"
            )
        )

        if read_response.success:
            student = read_response.student
            student.cheating_count = current_count
            
            # If this is the 3rd offense, terminate immediately
            if current_count >= 3:
                student.status = "terminated"
                student.ese_marks = 0
                
                # FIXED: Properly move from active to completed students
                if roll_no in active_students:
                    active_students[roll_no]['status'] = 'terminated'
                    active_students[roll_no]['cheating_count'] = current_count
                    
                    completed_students[roll_no] = {
                        'name': active_students[roll_no]['name'],
                        'session_id': active_students[roll_no]['session_id'],
                        'start_time': active_students[roll_no]['start_time'],
                        'submission_time': time.time(),
                        'final_score': 0,
                        'base_score': 0,
                        'submit_type': 'terminated',
                        'cheating_count': current_count
                    }
                    
                    # Remove from active students
                    del active_students[roll_no]
                
                add_system_log(f"🚫 EXAM TERMINATED: {roll_no} - 3rd cheating offense, final score: 0")
                
                # Update Excel immediately for terminated student
                await update_excel_file_for_terminated(roll_no, current_count)
            else:
                # Just update the cheating count, penalty will be applied during submission
                if roll_no in active_students:
                    active_students[roll_no]['cheating_count'] = current_count

            # Update student data in consistency service
            await stub.WriteStudentData(
                pb2.WriteStudentDataRequest(
                    roll_no=roll_no,
                    student_data=student,
                    requester_type="system"
                )
            )

        await channel.close()

    except grpc.RpcError as e:
        add_system_log(f"❌ Failed to handle cheating for {roll_no}: {e}")

async def update_excel_file_for_terminated(roll_no: str, cheating_count: int):
    """Update Excel file for terminated students"""
    try:
        if not current_session_id:
            return
            
        os.makedirs("Results", exist_ok=True)
        filename = f"Results/exam_results_{current_session_id}.xlsx"
        
        # Load or create DataFrame
        if os.path.exists(filename):
            try:
                df = pd.read_excel(filename, sheet_name='Results')
            except:
                df = pd.DataFrame(columns=[
                    'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                    'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
                ])
        else:
            df = pd.DataFrame(columns=[
                'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
            ])
        
        # Get student info
        student_info = completed_students.get(roll_no, active_students.get(roll_no, {}))
        
        new_data = {
            'Roll Number': roll_no,
            'Name': student_info.get('name', 'Unknown'),
            'Base Score': 0,
            'Final Score': 0,
            'Submit Type': 'terminated',
            'Submission Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Cheating Count': cheating_count,
            'Status': f'TERMINATED (Cheating - {cheating_count} offenses)',
            'Penalty Applied': 'EXAM TERMINATED'
        }
        
        # Update or add row
        existing_row = df[df['Roll Number'] == roll_no]
        
        if not existing_row.empty:
            for col, value in new_data.items():
                df.loc[df['Roll Number'] == roll_no, col] = value
        else:
            new_row_df = pd.DataFrame([new_data])
            df = pd.concat([df, new_row_df], ignore_index=True)
        
        # Save to Excel
        with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, sheet_name='Results', index=False)
        
        add_system_log(f"📊 Updated Excel file for TERMINATED student {roll_no}")
        
    except Exception as e:
        add_system_log(f"❌ Failed to update Excel for terminated student {roll_no}: {e}")

# FIXED: Clear all previous data function
def clear_previous_exam_data():
    """FIXED: Clear all previous exam session data"""
    global active_students, completed_students, cheating_offenses, exam_results
    
    add_system_log("🧹 CLEARING PREVIOUS EXAM DATA")
    
    # Clear all dictionaries
    previous_active = len(active_students)
    previous_completed = len(completed_students)
    previous_cheating = len(cheating_offenses)
    
    active_students.clear()
    completed_students.clear()
    cheating_offenses.clear()  # Clear cheating records
    exam_results.clear()
    
    add_system_log(f"✅ CLEARED: {previous_active} active students, {previous_completed} completed students, {previous_cheating} cheating records")

class ExamServiceServicer(pb2_grpc.ExamServiceServicer):
    def __init__(self):
        self.submission_lock = threading.Lock()
        
    async def StartExam(self, request, context):
        """Start exam for a student"""
        global current_session_id
        
        roll_no = request.roll_no
        student_name = request.student_name
        
        add_system_log(f"📝 Exam start request from {student_name} ({roll_no})")
        
        # Initialize cheating count for new student
        if roll_no not in cheating_offenses:
            cheating_offenses[roll_no] = 0
        
        # Check if there's an active exam session
        active_session = None
        for session_id, session in exam_sessions.items():
            if session.get('status') == 'active' and time.time() < session.get('end_time', 0):
                active_session = session_id
                current_session_id = session_id
                break
        
        if not active_session:
            add_system_log(f"❌ No active exam session for {roll_no}")
            return pb2.StartExamResponse(
                success=False,
                message="No active exam session. Please wait for teacher to start the exam.",
                exam_end_time=0,
                session_id=""
            )
        
        # Check if student already started
        if roll_no in active_students:
            add_system_log(f"⚠️ Student {roll_no} already started exam")
            return pb2.StartExamResponse(
                success=False,
                message="You have already started the exam.",
                exam_end_time=exam_sessions[active_session]['end_time'],
                session_id=active_session
            )
        
        # Register student with consistency service
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            student_data = pb2.Student(
                roll_no=roll_no,
                name=student_name,
                isa_marks=0,
                mse_marks=0,
                ese_marks=0,  # This will store exam marks now
                status="active",
                cheating_count=0
            )
            
            write_response = await stub.WriteStudentData(
                pb2.WriteStudentDataRequest(
                    roll_no=roll_no,
                    student_data=student_data,
                    requester_type="system"
                )
            )
            
            await channel.close()
            
            if not write_response.success:
                add_system_log(f"❌ Failed to register student {roll_no} in consistency service")
                return pb2.StartExamResponse(
                    success=False,
                    message="Failed to register student data.",
                    exam_end_time=0,
                    session_id=""
                )
                
        except grpc.RpcError as e:
            add_system_log(f"❌ Failed to register student {roll_no}: {e}")
            return pb2.StartExamResponse(
                success=False,
                message="System error during registration.",
                exam_end_time=0,
                session_id=""
            )
        
        # Add to active students
        active_students[roll_no] = {
            'name': student_name,
            'session_id': active_session,
            'start_time': time.time(),
            'status': 'active',
            'cheating_count': 0
        }
        
        add_system_log(f"✅ Student {roll_no} started exam successfully")
        return pb2.StartExamResponse(
            success=True,
            message="Exam started successfully. Good luck!",
            exam_end_time=exam_sessions[active_session]['end_time'],
            session_id=active_session
        )
    
    async def GetExamQuestions(self, request, context):
        """Get exam questions for a student"""
        roll_no = request.roll_no
        session_id = request.session_id
        
        if roll_no not in active_students:
            add_system_log(f"❌ Questions request from inactive student {roll_no}")
            return pb2.GetExamQuestionsResponse(
                success=False,
                questions=[],
                time_remaining=0
            )
        
        if session_id not in exam_sessions:
            add_system_log(f"❌ Invalid session {session_id} for student {roll_no}")
            return pb2.GetExamQuestionsResponse(
                success=False,
                questions=[],
                time_remaining=0
            )
        
        session = exam_sessions[session_id]
        time_remaining = max(0, session['end_time'] - time.time())
        
        add_system_log(f"📋 Sent questions to student {roll_no}")
        return pb2.GetExamQuestionsResponse(
            success=True,
            questions=exam_questions,
            time_remaining=time_remaining
        )
    
    async def SubmitExam(self, request, context):
        """Submit exam answers with cheating penalty application"""
        roll_no = request.roll_no
        session_id = request.session_id
        answers = request.answers
        submit_type = request.submit_type
        
        add_system_log(f"📤 Exam submission from {roll_no}, type: {submit_type}")
        
        # Check if student is active
        if roll_no not in active_students:
            add_system_log(f"❌ Submission from inactive student {roll_no}")
            return pb2.SubmitExamResponse(
                success=False,
                message="Student not found in active list.",
                final_score=0
            )
        
        # Check if already submitted
        if active_students[roll_no].get('status') == 'submitted':
            add_system_log(f"⚠️ Duplicate submission from {roll_no}")
            return pb2.SubmitExamResponse(
                success=False,
                message="Exam already submitted.",
                final_score=0
            )
        
        # Calculate base score
        base_score = self._calculate_score(answers)
        
        # Apply cheating penalties if any
        current_cheating_count = cheating_offenses.get(roll_no, 0)
        final_score = self._apply_cheating_penalty(base_score, current_cheating_count, roll_no)
        
        try:
            # Use load balancer for submission processing
            channel = grpc.aio.insecure_channel(LOAD_BALANCER_URL)
            stub = pb2_grpc.LoadBalancerServiceStub(channel)
            
            route_response = await stub.RouteSubmission(
                pb2.RouteSubmissionRequest(
                    submission=request,
                    current_load=len([s for s in active_students.values() if s.get('status') == 'active'])
                )
            )
            
            await channel.close()
            
            if route_response.result.success or True:  # Process locally if load balancer fails
                # Update student status
                active_students[roll_no]['status'] = 'submitted'
                active_students[roll_no]['submission_time'] = time.time()
                active_students[roll_no]['final_score'] = final_score
                active_students[roll_no]['base_score'] = base_score
                active_students[roll_no]['cheating_count'] = current_cheating_count
                
                # Move to completed students
                completed_students[roll_no] = {
                    'name': active_students[roll_no]['name'],
                    'session_id': session_id,
                    'start_time': active_students[roll_no]['start_time'],
                    'submission_time': time.time(),
                    'final_score': final_score,
                    'base_score': base_score,
                    'submit_type': submit_type,
                    'cheating_count': current_cheating_count
                }
                
                # Update score in consistency service
                await self._update_student_score(roll_no, final_score, current_cheating_count)
                
                # Update Excel file
                await self._update_excel_file(roll_no, final_score, base_score, current_cheating_count, submit_type)
                
                # Generate appropriate message based on cheating offenses
                penalty_message = ""
                if current_cheating_count > 0:
                    penalty_reduction = base_score - final_score
                    penalty_message = f" (Original: {base_score}, Penalty: -{penalty_reduction} for {current_cheating_count} cheating offense(s))"
                
                result_message = f"Exam submitted successfully! Your final score: {final_score}/100{penalty_message}"
                
                add_system_log(f"✅ Student {roll_no} submitted exam successfully, final score: {final_score}, base score: {base_score}, cheating count: {current_cheating_count}")
                
                return pb2.SubmitExamResponse(
                    success=True,
                    message=result_message,
                    final_score=final_score
                )
            else:
                add_system_log(f"❌ Submission processing failed for {roll_no}")
                return route_response.result
            
        except grpc.RpcError as e:
            add_system_log(f"❌ Submission routing failed for {roll_no}: {e}")
            return pb2.SubmitExamResponse(
                success=False,
                message="System error during submission.",
                final_score=0
            )
    
    async def GetStudentStatus(self, request, context):
        """Get current status of a student"""
        roll_no = request.roll_no
        
        # Check if student is in active or completed list
        student_info = None
        if roll_no in active_students:
            student_info = active_students[roll_no]
        elif roll_no in completed_students:
            student_info = completed_students[roll_no]
        
        if not student_info:
            return pb2.GetStudentStatusResponse(
                success=False,
                student=pb2.Student(),
                time_remaining=0
            )
        
        # Get student data from consistency service
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            read_response = await stub.ReadStudentData(
                pb2.ReadStudentDataRequest(
                    roll_no=roll_no,
                    requester_type="system"
                )
            )
            
            await channel.close()
            
            if read_response.success:
                # Calculate time remaining
                session_id = student_info['session_id']
                time_remaining = 0
                if session_id in exam_sessions and roll_no in active_students:
                    time_remaining = max(0, exam_sessions[session_id]['end_time'] - time.time())
                
                return pb2.GetStudentStatusResponse(
                    success=True,
                    student=read_response.student,
                    time_remaining=time_remaining
                )
            
        except grpc.RpcError as e:
            add_system_log(f"❌ Failed to get student status for {roll_no}: {e}")
        
        return pb2.GetStudentStatusResponse(
            success=False,
            student=pb2.Student(),
            time_remaining=0
        )
    
    def _calculate_score(self, answers: List[pb2.Answer]) -> int:
        """Calculate exam score based on answers"""
        score = 0
        correct_answers = {q.question_id: q.correct_answer for q in exam_questions}
        
        for answer in answers:
            if answer.question_id in correct_answers:
                if answer.selected_option == correct_answers[answer.question_id]:
                    score += 10
        
        return score
    
    def _apply_cheating_penalty(self, base_score: int, cheating_count: int, roll_no: str) -> int:
        """Apply cheating penalty based on offense count"""
        if cheating_count == 0:
            return base_score
        elif cheating_count == 1:
            # First offense: 25% reduction
            penalty = int(base_score * 0.25)
            final_score = max(0, base_score - penalty)
            add_system_log(f"⚖️ CHEATING PENALTY APPLIED: {roll_no} - 1st offense, {base_score} → {final_score} (-{penalty})")
            return final_score
        elif cheating_count == 2:
            # Second offense: 50% reduction
            penalty = int(base_score * 0.50)
            final_score = max(0, base_score - penalty)
            add_system_log(f"⚖️ CHEATING PENALTY APPLIED: {roll_no} - 2nd offense, {base_score} → {final_score} (-{penalty})")
            return final_score
        else:
            # Third+ offense: Exam terminated (0 score)
            add_system_log(f"🚫 CHEATING PENALTY APPLIED: {roll_no} - 3rd+ offense, exam terminated (0 score)")
            return 0
    
    async def _update_student_score(self, roll_no: str, final_score: int, cheating_count: int):
        """Update student's ESE marks with calculated score"""
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            # First read current data
            read_response = await stub.ReadStudentData(
                pb2.ReadStudentDataRequest(
                    roll_no=roll_no,
                    requester_type="system"
                )
            )
            
            if read_response.success:
                student = read_response.student
                student.ese_marks = final_score  # ESE now stores final exam score
                student.status = "submitted"
                student.cheating_count = cheating_count
                
                # Write updated data
                await stub.WriteStudentData(
                    pb2.WriteStudentDataRequest(
                        roll_no=roll_no,
                        student_data=student,
                        requester_type="system"
                    )
                )
            
            await channel.close()
            
        except grpc.RpcError as e:
            add_system_log(f"❌ Failed to update score for {roll_no}: {e}")
    
    async def _update_excel_file(self, roll_no: str, final_score: int, base_score: int, cheating_count: int, submit_type: str):
        """Update Excel file with student results"""
        try:
            if not current_session_id:
                return
                
            # Ensure Results directory exists
            os.makedirs("Results", exist_ok=True)
            filename = f"Results/exam_results_{current_session_id}.xlsx"
            
            # Create or load existing file
            if os.path.exists(filename):
                try:
                    df = pd.read_excel(filename, sheet_name=0)  # Read first sheet regardless of name
                except Exception:
                    df = pd.DataFrame(columns=[
                        'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                        'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
                    ])
            else:
                df = pd.DataFrame(columns=[
                    'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                    'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
                ])
            
            # Get student info
            student_info = completed_students.get(roll_no, active_students.get(roll_no, {}))
            
            # Calculate penalty
            penalty = base_score - final_score
            penalty_text = f"-{penalty}" if penalty > 0 else "None"
            status_text = "Submitted"
            if cheating_count >= 3:
                status_text = "Terminated (Cheating)"
            elif cheating_count > 0:
                status_text = f"Submitted ({cheating_count} offense(s))"
            
            # Update or add row
            existing_row = df[df['Roll Number'] == roll_no]
            
            new_data = {
                'Roll Number': roll_no,
                'Name': student_info.get('name', 'Unknown'),
                'Base Score': base_score,
                'Final Score': final_score,
                'Submit Type': submit_type,
                'Submission Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Cheating Count': cheating_count,
                'Status': status_text,
                'Penalty Applied': penalty_text
            }
            
            if not existing_row.empty:
                # Update existing row
                for col, value in new_data.items():
                    df.loc[df['Roll Number'] == roll_no, col] = value
            else:
                # Add new row
                new_row_df = pd.DataFrame([new_data])
                df = pd.concat([df, new_row_df], ignore_index=True)
            
            # Save to Excel with proper error handling
            try:
                with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
                    df.to_excel(writer, sheet_name='Results', index=False)
                    
                    # Add summary sheet
                    summary_data = {
                        'Metric': ['Total Students', 'Average Final Score', 'Students with Penalties', 'Terminated Students'],
                        'Value': [
                            len(df),
                            df['Final Score'].mean() if len(df) > 0 else 0,
                            len(df[df['Cheating Count'] > 0]),
                            len(df[df['Cheating Count'] >= 3])
                        ]
                    }
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                add_system_log(f"Updated Excel file {filename} for student {roll_no} - Final: {final_score}, Base: {base_score}, Penalty: {penalty}")
                
            except PermissionError:
                add_system_log(f"Excel file {filename} is open - cannot update for {roll_no}")
            except Exception as e:
                add_system_log(f"Error saving Excel file for {roll_no}: {e}")
            
        except Exception as e:
            add_system_log(f"Failed to update Excel file: {e}")

class TeacherServiceServicer(pb2_grpc.TeacherServiceServicer):
    async def StartExamSession(self, request, context):
        """FIXED: Start a new exam session with proper data clearing"""
        global current_session_id
        
        duration_minutes = request.duration_minutes
        exam_title = request.exam_title
        
        add_system_log(f"Starting new exam session: {exam_title}, duration: {duration_minutes} minutes")
        
        # Check if there's already an active session
        for session_id, session in exam_sessions.items():
            if session.get('status') == 'active' and time.time() < session.get('end_time', 0):
                add_system_log(f"Cannot start exam - session {session_id} already active")
                return pb2.StartExamSessionResponse(
                    success=False,
                    message="Another exam session is already active.",
                    session_id="",
                    exam_end_time=0
                )
        
        # FIXED: Stop previous cheating detection and clear data
        await stop_cheating_detection_system()
        clear_previous_exam_data()
        
        # Create new session
        session_id = str(uuid.uuid4())
        end_time = time.time() + (duration_minutes * 60)
        current_session_id = session_id
        
        exam_sessions[session_id] = {
            'title': exam_title,
            'start_time': time.time(),
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'status': 'active'
        }
        
        # Create new Excel file for this session
        await self._create_excel_file(session_id, exam_title)
        
        # FIXED: Start cheating detection system
        await start_cheating_detection_system()
        
        add_system_log(f"Started exam session: {exam_title} ({session_id}), duration: {duration_minutes} minutes")
        
        # Start session monitor
        asyncio.create_task(self._monitor_session(session_id))
        
        return pb2.StartExamSessionResponse(
            success=True,
            message=f"Exam session '{exam_title}' started successfully.",
            session_id=session_id,
            exam_end_time=end_time
        )
    
    async def EndExamSession(self, request, context):
        """FIXED: End an exam session and stop cheating detection"""
        session_id = request.session_id
        
        if session_id not in exam_sessions:
            add_system_log(f"Attempt to end non-existent session {session_id}")
            return pb2.EndExamSessionResponse(
                success=False,
                message="Session not found."
            )
        
        # FIXED: Stop cheating detection system
        await stop_cheating_detection_system()
        
        exam_sessions[session_id]['status'] = 'ended'
        exam_sessions[session_id]['actual_end_time'] = time.time()
        
        # Auto-submit any remaining active students
        await self._auto_submit_remaining_students(session_id)
        
        add_system_log(f"Ended exam session: {session_id}")
        
        return pb2.EndExamSessionResponse(
            success=True,
            message="Exam session ended successfully."
        )
    
    async def GetAllStudentMarks(self, request, context):
        """Get marks for students who have completed the exam"""
        try:
            students = []
            
            for roll_no, student_info in completed_students.items():
                try:
                    channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
                    stub = pb2_grpc.ConsistencyServiceStub(channel)
                    
                    read_response = await stub.ReadStudentData(
                        pb2.ReadStudentDataRequest(
                            roll_no=roll_no,
                            requester_type="teacher"
                        )
                    )
                    
                    await channel.close()
                    
                    if read_response.success:
                        student = read_response.student
                        students.append(student)
                
                except grpc.RpcError as e:
                    add_system_log(f"Failed to get data for {roll_no}: {e}")
                    # Create a basic student record if consistency service fails
                    students.append(pb2.Student(
                        roll_no=roll_no,
                        name=student_info.get('name', 'Unknown'),
                        isa_marks=0,
                        mse_marks=0,
                        ese_marks=student_info.get('final_score', 0),
                        status="submitted" if student_info.get('submit_type') != 'terminated' else "terminated",
                        cheating_count=student_info.get('cheating_count', 0)
                    ))
            
            return pb2.GetAllStudentMarksResponse(
                success=True,
                students=students
            )
            
        except Exception as e:
            add_system_log(f"Failed to get student marks: {e}")
            return pb2.GetAllStudentMarksResponse(
                success=False,
                students=[]
            )
    
    async def UpdateStudentMarks(self, request, context):
        """Update exam marks for a specific student - with proper concurrency handling"""
        try:
            # Use Ricart-Agrawala for mutual exclusion
            channel_ra = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
            stub_ra = pb2_grpc.RicartAgrawalaServiceStub(channel_ra)
            
            # Request critical section
            cs_response = await stub_ra.RequestCS(
                pb2.RequestCSRequest(
                    roll_no=f"teacher_marks_{request.roll_no}",
                    lamport_timestamp=int(time.time() * 1000000)
                )
            )
            
            if not cs_response.success:
                await channel_ra.close()
                add_system_log(f"Failed to acquire lock for updating marks for {request.roll_no}")
                return pb2.UpdateStudentMarksResponse(
                    success=False,
                    message="Failed to acquire lock for update. Another teacher may be editing this student's marks.",
                    updated_student=pb2.Student()
                )
            
            add_system_log(f"Acquired lock for updating marks for {request.roll_no} by {request.updated_by}")
            
            try:
                # Update student data through consistency service
                channel_cs = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
                stub_cs = pb2_grpc.ConsistencyServiceStub(channel_cs)
                
                # Read current data first
                read_response = await stub_cs.ReadStudentData(
                    pb2.ReadStudentDataRequest(
                        roll_no=request.roll_no,
                        requester_type="teacher"
                    )
                )
                
                if read_response.success:
                    student = read_response.student
                    old_score = student.ese_marks
                    # For exam system, only ESE marks (exam score) should be editable
                    student.ese_marks = request.ese_marks
                    
                    # Write updated data
                    write_response = await stub_cs.WriteStudentData(
                        pb2.WriteStudentDataRequest(
                            roll_no=request.roll_no,
                            student_data=student,
                            requester_type="teacher"
                        )
                    )
                    
                    await channel_cs.close()
                    
                    if write_response.success:
                        # Update in completed students
                        if request.roll_no in completed_students:
                            completed_students[request.roll_no]['final_score'] = request.ese_marks
                        
                        # Update Excel file
                        await self._update_excel_marks_fixed(request.roll_no, request.ese_marks, old_score)
                        
                        add_system_log(f"Updated marks for {request.roll_no} from {old_score} to {request.ese_marks} by {request.updated_by}")
                        return pb2.UpdateStudentMarksResponse(
                            success=True,
                            message="Marks updated successfully.",
                            updated_student=write_response.updated_student
                        )
                else:
                    await channel_cs.close()
                    add_system_log(f"Student {request.roll_no} not found for marks update")
                    return pb2.UpdateStudentMarksResponse(
                        success=False,
                        message="Student not found.",
                        updated_student=pb2.Student()
                    )
            
            finally:
                # Release critical section
                await stub_ra.ReleaseCS(
                    pb2.ReleaseCSRequest(
                        roll_no=f"teacher_marks_{request.roll_no}",
                        lamport_timestamp=int(time.time() * 1000000)
                    )
                )
                await channel_ra.close()
                add_system_log(f"Released lock for updating marks for {request.roll_no}")
            
        except grpc.RpcError as e:
            add_system_log(f"Failed to update marks for {request.roll_no}: {e}")
            return pb2.UpdateStudentMarksResponse(
                success=False,
                message="System error during update.",
                updated_student=pb2.Student()
            )
    
    async def GetExamResults(self, request, context):
        """Get comprehensive exam results with statistics"""
        try:
            students = []
            
            # Get all completed students
            for roll_no, student_info in completed_students.items():
                try:
                    channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
                    stub = pb2_grpc.ConsistencyServiceStub(channel)
                    
                    read_response = await stub.ReadStudentData(
                        pb2.ReadStudentDataRequest(
                            roll_no=roll_no,
                            requester_type="teacher"
                        )
                    )
                    
                    await channel.close()
                    
                    if read_response.success:
                        student = read_response.student
                        students.append(student)
                
                except grpc.RpcError as e:
                    add_system_log(f"Failed to get exam results for {roll_no}: {e}")
                    # Create a basic student record if consistency service fails
                    students.append(pb2.Student(
                        roll_no=roll_no,
                        name=student_info.get('name', 'Unknown'),
                        isa_marks=0,
                        mse_marks=0,
                        ese_marks=student_info.get('final_score', 0),
                        status="submitted" if student_info.get('submit_type') != 'terminated' else "terminated",
                        cheating_count=student_info.get('cheating_count', 0)
                    ))

            # Calculate statistics
            if students:
                total_students = len(students)
                completed_students_count = len(students)
                cheating_incidents = sum(s.cheating_count for s in students)
                
                if total_students > 0:
                    average_score = sum(s.ese_marks for s in students) / total_students
                    passed_students = len([s for s in students if s.ese_marks >= 40])
                else:
                    average_score = 0
                    passed_students = 0
                
                statistics = pb2.ExamStatistics(
                    total_students=total_students,
                    completed_students=completed_students_count,
                    cheating_incidents=cheating_incidents,
                    average_score=average_score,
                    passed_students=passed_students
                )
                
                return pb2.GetExamResultsResponse(
                    success=True,
                    students=students,
                    statistics=statistics
                )
            
            return pb2.GetExamResultsResponse(
                success=False,
                students=[],
                statistics=pb2.ExamStatistics()
            )
            
        except Exception as e:
            add_system_log(f"Failed to get exam results: {e}")
            return pb2.GetExamResultsResponse(
                success=False,
                students=[],
                statistics=pb2.ExamStatistics()
            )
    
    async def _create_excel_file(self, session_id: str, exam_title: str):
        """Create new Excel file for exam session"""
        try:
            os.makedirs("Results", exist_ok=True)
            filename = f"Results/exam_results_{session_id}.xlsx"
            
            # Create empty DataFrame with headers
            df = pd.DataFrame(columns=[
                'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
            ])
            
            # Save with proper structure
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Results', index=False)
                
                # Create metadata sheet
                metadata = pd.DataFrame({
                    'Property': ['Session ID', 'Exam Title', 'Start Time', 'Duration (minutes)', 'Status'],
                    'Value': [session_id, exam_title, 
                             datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             exam_sessions[session_id]['duration_minutes'],
                             'Active']
                })
                metadata.to_excel(writer, sheet_name='Metadata', index=False)
            
            add_system_log(f"Created Excel file: {filename}")
            
        except Exception as e:
            add_system_log(f"Failed to create Excel file: {e}")
    
    async def _update_excel_marks_fixed(self, roll_no: str, new_score: int, old_score: int):
        """Update Excel file when teacher changes marks"""
        try:
            if not current_session_id:
                add_system_log(f"No current session ID for updating {roll_no}")
                return
                
            os.makedirs("Results", exist_ok=True)
            filename = f"Results/exam_results_{current_session_id}.xlsx"
            
            if os.path.exists(filename):
                try:
                    # Read existing data
                    df = pd.read_excel(filename, sheet_name='Results')
                    
                    # Check if student exists in Excel
                    student_mask = df['Roll Number'] == roll_no
                    
                    if student_mask.any():
                        # Update existing student's score
                        df.loc[student_mask, 'Final Score'] = new_score
                        df.loc[student_mask, 'Status'] = 'Updated by Teacher'
                        df.loc[student_mask, 'Submission Time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Recalculate penalty if base score exists
                        if 'Base Score' in df.columns:
                            base_score = df.loc[student_mask, 'Base Score'].iloc[0]
                            penalty = max(0, base_score - new_score)
                            df.loc[student_mask, 'Penalty Applied'] = f"-{penalty}" if penalty > 0 else "None"
                        
                        add_system_log(f"Updated existing student {roll_no} in Excel: {old_score} → {new_score}")
                    else:
                        # Add new student entry
                        student_info = completed_students.get(roll_no, active_students.get(roll_no, {}))
                        new_row = pd.DataFrame([{
                            'Roll Number': roll_no,
                            'Name': student_info.get('name', 'Unknown'),
                            'Base Score': new_score,
                            'Final Score': new_score,
                            'Submit Type': 'manual',
                            'Submission Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'Cheating Count': cheating_offenses.get(roll_no, 0),
                            'Status': 'Added by Teacher',
                            'Penalty Applied': 'None'
                        }])
                        df = pd.concat([df, new_row], ignore_index=True)
                        add_system_log(f"Added new student {roll_no} to Excel with score {new_score}")
                    
                    # Save the updated Excel file
                    with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
                        df.to_excel(writer, sheet_name='Results', index=False)
                        
                        # Update summary sheet
                        try:
                            summary_data = pd.DataFrame({
                                'Metric': ['Total Students', 'Average Final Score', 'Students with Penalties', 'Terminated Students', 'Last Updated'],
                                'Value': [
                                    len(df),
                                    f"{df['Final Score'].mean():.2f}" if len(df) > 0 else "0",
                                    len(df[df['Cheating Count'] > 0]),
                                    len(df[df['Cheating Count'] >= 3]),
                                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                ]
                            })
                            summary_data.to_excel(writer, sheet_name='Summary', index=False)
                        except Exception as summary_error:
                            add_system_log(f"Failed to update summary sheet: {summary_error}")
                    
                    add_system_log(f"Successfully updated Excel file for {roll_no}: score changed to {new_score}")
                    
                except PermissionError:
                    add_system_log(f"Excel file {filename} is currently open - cannot update {roll_no}")
                except Exception as read_error:
                    add_system_log(f"Error reading/updating Excel file for {roll_no}: {read_error}")
                    
            else:
                add_system_log(f"Excel file {filename} not found for updating {roll_no}")
                
        except Exception as e:
            add_system_log(f"Failed to update Excel marks for {roll_no}: {e}")
    
    async def _monitor_session(self, session_id: str):
        """Monitor exam session and auto-end when time expires"""
        session = exam_sessions.get(session_id, {})
        end_time = session.get('end_time', time.time())
        
        while time.time() < end_time:
            await asyncio.sleep(10)  # Check every 10 seconds
        
        # Auto-end session
        if exam_sessions.get(session_id, {}).get('status') == 'active':
            await stop_cheating_detection_system()
            exam_sessions[session_id]['status'] = 'ended'
            exam_sessions[session_id]['actual_end_time'] = time.time()
            await self._auto_submit_remaining_students(session_id)
            add_system_log(f"Auto-ended exam session: {session_id}")
    
    async def _auto_submit_remaining_students(self, session_id: str):
        """Auto-submit exams for students who haven't submitted"""
        remaining_students = [
            roll_no for roll_no, data in active_students.items()
            if data.get('session_id') == session_id and data.get('status') == 'active'
        ]
        
        for roll_no in remaining_students:
            # Calculate current cheating penalties
            current_cheating_count = cheating_offenses.get(roll_no, 0)
            base_score = 0  # No answers provided
            final_score = self._apply_cheating_penalty_static(base_score, current_cheating_count)
            
            # Update student status
            active_students[roll_no]['status'] = 'auto_submitted'
            
            # Move to completed students
            completed_students[roll_no] = {
                'name': active_students[roll_no]['name'],
                'session_id': session_id,
                'start_time': active_students[roll_no]['start_time'],
                'submission_time': time.time(),
                'final_score': final_score,
                'base_score': base_score,
                'submit_type': 'auto',
                'cheating_count': current_cheating_count
            }
            
            # Update consistency service
            await self._update_student_score_direct(roll_no, final_score, current_cheating_count)
            
            # Update Excel file
            await self._update_excel_file_direct(roll_no, final_score, base_score, current_cheating_count, 'auto')
            
            add_system_log(f"Auto-submitted exam for {roll_no} - Final score: {final_score} (Base: {base_score}, Cheating: {current_cheating_count})")
    
    def _apply_cheating_penalty_static(self, base_score: int, cheating_count: int) -> int:
        """Static method to apply cheating penalty"""
        if cheating_count == 0:
            return base_score
        elif cheating_count == 1:
            return max(0, base_score - int(base_score * 0.25))
        elif cheating_count == 2:
            return max(0, base_score - int(base_score * 0.50))
        else:
            return 0  # Terminated
    
    async def _update_student_score_direct(self, roll_no: str, final_score: int, cheating_count: int):
        """Direct update of student score"""
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            read_response = await stub.ReadStudentData(
                pb2.ReadStudentDataRequest(
                    roll_no=roll_no,
                    requester_type="system"
                )
            )
            
            if read_response.success:
                student = read_response.student
                student.ese_marks = final_score
                student.status = "submitted"
                student.cheating_count = cheating_count
                
                await stub.WriteStudentData(
                    pb2.WriteStudentDataRequest(
                        roll_no=roll_no,
                        student_data=student,
                        requester_type="system"
                    )
                )
            
            await channel.close()
            
        except grpc.RpcError as e:
            add_system_log(f"Failed to update score for {roll_no}: {e}")
    
    async def _update_excel_file_direct(self, roll_no: str, final_score: int, base_score: int, cheating_count: int, submit_type: str):
        """Direct update to Excel file with proper structure"""
        try:
            if not current_session_id:
                return
                
            os.makedirs("Results", exist_ok=True)
            filename = f"Results/exam_results_{current_session_id}.xlsx"
            
            # Load existing file or create new structure
            if os.path.exists(filename):
                try:
                    df = pd.read_excel(filename, sheet_name='Results')
                except:
                    df = pd.DataFrame(columns=[
                        'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                        'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
                    ])
            else:
                df = pd.DataFrame(columns=[
                    'Roll Number', 'Name', 'Base Score', 'Final Score', 'Submit Type', 
                    'Submission Time', 'Cheating Count', 'Status', 'Penalty Applied'
                ])
            
            student_info = completed_students.get(roll_no, active_students.get(roll_no, {}))
            
            # Calculate penalty and status
            penalty = base_score - final_score
            penalty_text = f"-{penalty}" if penalty > 0 else "None"
            
            if cheating_count >= 3:
                status_text = "Terminated (Cheating)"
            elif submit_type == 'auto':
                status_text = f"Auto Submitted ({cheating_count} offense(s))" if cheating_count > 0 else "Auto Submitted"
            else:
                status_text = f"Submitted ({cheating_count} offense(s))" if cheating_count > 0 else "Submitted"
            
            new_data = {
                'Roll Number': roll_no,
                'Name': student_info.get('name', 'Unknown'),
                'Base Score': base_score,
                'Final Score': final_score,
                'Submit Type': submit_type,
                'Submission Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Cheating Count': cheating_count,
                'Status': status_text,
                'Penalty Applied': penalty_text
            }
            
            # Check if student already exists
            existing_row = df[df['Roll Number'] == roll_no]
            
            if not existing_row.empty:
                # Update existing row
                for col, value in new_data.items():
                    df.loc[df['Roll Number'] == roll_no, col] = value
            else:
                # Add new row
                new_row_df = pd.DataFrame([new_data])
                df = pd.concat([df, new_row_df], ignore_index=True)
            
            # Save with proper structure
            with pd.ExcelWriter(filename, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, sheet_name='Results', index=False)
            
            add_system_log(f"Updated Excel file for {roll_no}: Final={final_score}, Base={base_score}, Cheating={cheating_count}")
            
        except Exception as e:
            add_system_log(f"Failed to update Excel file for {roll_no}: {e}")

class AdminServiceServicer(pb2_grpc.AdminServiceServicer):
    def __init__(self):
        self.max_logs = 1000
    
    async def GetSystemLogs(self, request, context):
        """Get recent system logs with enhanced filtering"""
        last_n = min(request.last_n_lines or 50, self.max_logs)
        service_filter = request.service_name
        
        # Filter logs by service name if specified
        filtered_logs = system_logs
        if service_filter:
            filtered_logs = [log for log in system_logs if service_filter.lower() in log.lower()]
        
        # Get recent logs
        recent_logs = filtered_logs[-last_n:] if filtered_logs else []
        
        return pb2.GetSystemLogsResponse(
            log_lines=recent_logs,
            timestamp=int(time.time())
        )
    
    async def GetServerMetrics(self, request, context):
        """Get current server metrics"""
        active_count = len([s for s in active_students.values() if s.get('status') == 'active'])
        completed_count = len(completed_students)
        
        return pb2.GetServerMetricsResponse(
            active_students=active_count,
            completed_submissions=completed_count,
            pending_requests=0,
            cpu_usage=0.0,
            memory_usage=0.0
        )
    
    async def GetActiveConnections(self, request, context):
        """Get active client connections"""
        connections = []
        
        # Add active students
        for roll_no, data in active_students.items():
            connections.append(
                pb2.ConnectionInfo(
                    client_id=roll_no,
                    connection_type="student",
                    connected_since=int(data.get('start_time', time.time())),
                    status=data.get('status', 'unknown')
                )
            )
        
        # Add completed students
        for roll_no, data in completed_students.items():
            connections.append(
                pb2.ConnectionInfo(
                    client_id=roll_no,
                    connection_type="student",
                    connected_since=int(data.get('start_time', time.time())),
                    status="completed"
                )
            )
        
        return pb2.GetActiveConnectionsResponse(
            connections=connections
        )

async def serve():
    """Start the main server with all services"""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=20))
    
    # Create service instances
    exam_service = ExamServiceServicer()
    teacher_service = TeacherServiceServicer()
    admin_service = AdminServiceServicer()
    
    # Add services to server
    pb2_grpc.add_ExamServiceServicer_to_server(exam_service, server)
    pb2_grpc.add_TeacherServiceServicer_to_server(teacher_service, server)
    pb2_grpc.add_AdminServiceServicer_to_server(admin_service, server)
    
    # Configure server address
    listen_addr = f'[::]:{MAIN_SERVER_PORT}'
    server.add_insecure_port(listen_addr)
    
    add_system_log(f"FIXED Main Server starting on port {MAIN_SERVER_PORT}")
    logger.info(f"Starting FIXED Main Server on {listen_addr}")
    
    # Start server
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        add_system_log("FIXED Main Server shutting down")
        await stop_cheating_detection_system()
        logger.info("Shutting down FIXED Main Server...")
        await server.stop(5)

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nFIXED Main Server stopped.")