#!/usr/bin/env python3
"""
Main Server - Primary coordinator for the distributed exam system
Handles exam flow, load balancing, and coordinates with other services
"""

import asyncio
import grpc
import time
import uuid
import logging
import threading
from concurrent import futures
from typing import Dict, List, Optional
import json

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

class ExamServiceServicer(pb2_grpc.ExamServiceServicer):
    def __init__(self):
        self.submission_lock = threading.Lock()
        
    async def StartExam(self, request, context):
        """Start exam for a student"""
        roll_no = request.roll_no
        student_name = request.student_name
        
        logger.info(f"Exam start request from {student_name} ({roll_no})")
        
        # Check if there's an active exam session
        active_session = None
        for session_id, session in exam_sessions.items():
            if session.get('status') == 'active' and time.time() < session.get('end_time', 0):
                active_session = session_id
                break
        
        if not active_session:
            return pb2.StartExamResponse(
                success=False,
                message="No active exam session. Please wait for teacher to start the exam.",
                exam_end_time=0,
                session_id=""
            )
        
        # Check if student already started
        if roll_no in active_students:
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
                ese_marks=0,
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
                return pb2.StartExamResponse(
                    success=False,
                    message="Failed to register student data.",
                    exam_end_time=0,
                    session_id=""
                )
                
        except grpc.RpcError as e:
            logger.error(f"Failed to register student {roll_no}: {e}")
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
            'status': 'active'
        }
        
        # Start cheating monitor for this student
        asyncio.create_task(self._monitor_cheating(roll_no, active_session))
        
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
            return pb2.GetExamQuestionsResponse(
                success=False,
                questions=[],
                time_remaining=0
            )
        
        if session_id not in exam_sessions:
            return pb2.GetExamQuestionsResponse(
                success=False,
                questions=[],
                time_remaining=0
            )
        
        session = exam_sessions[session_id]
        time_remaining = max(0, session['end_time'] - time.time())
        
        return pb2.GetExamQuestionsResponse(
            success=True,
            questions=exam_questions,
            time_remaining=time_remaining
        )
    
    async def SubmitExam(self, request, context):
        """Submit exam answers"""
        roll_no = request.roll_no
        session_id = request.session_id
        answers = request.answers
        submit_type = request.submit_type
        
        logger.info(f"Exam submission from {roll_no}, type: {submit_type}")
        
        # Check if student is active
        if roll_no not in active_students:
            return pb2.SubmitExamResponse(
                success=False,
                message="Student not found in active list.",
                final_score=0
            )
        
        # Check if already submitted
        if active_students[roll_no].get('status') == 'submitted':
            return pb2.SubmitExamResponse(
                success=False,
                message="Exam already submitted.",
                final_score=0
            )
        
        # Use load balancer for submission processing
        try:
            channel = grpc.aio.insecure_channel(LOAD_BALANCER_URL)
            stub = pb2_grpc.LoadBalancerServiceStub(channel)
            
            route_response = await stub.RouteSubmission(
                pb2.RouteSubmissionRequest(
                    submission=request,
                    current_load=len([s for s in active_students.values() if s.get('status') == 'active'])
                )
            )
            
            await channel.close()
            
            if route_response.result.success:
                # Update student status
                active_students[roll_no]['status'] = 'submitted'
                active_students[roll_no]['submission_time'] = time.time()
                
                # Calculate and update final score in consistency service
                score = self._calculate_score(answers)
                await self._update_student_score(roll_no, score)
            
            return route_response.result
            
        except grpc.RpcError as e:
            logger.error(f"Submission routing failed for {roll_no}: {e}")
            return pb2.SubmitExamResponse(
                success=False,
                message="System error during submission.",
                final_score=0
            )
    
    async def GetStudentStatus(self, request, context):
        """Get current status of a student"""
        roll_no = request.roll_no
        
        if roll_no not in active_students:
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
                session_id = active_students[roll_no]['session_id']
                time_remaining = 0
                if session_id in exam_sessions:
                    time_remaining = max(0, exam_sessions[session_id]['end_time'] - time.time())
                
                return pb2.GetStudentStatusResponse(
                    success=True,
                    student=read_response.student,
                    time_remaining=time_remaining
                )
            
        except grpc.RpcError as e:
            logger.error(f"Failed to get student status for {roll_no}: {e}")
        
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
    
    async def _update_student_score(self, roll_no: str, score: int):
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
                student.ese_marks = score
                student.status = "submitted"
                
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
            logger.error(f"Failed to update score for {roll_no}: {e}")
    
    async def _monitor_cheating(self, roll_no: str, session_id: str):
        """Monitor student for cheating behavior"""
        session = exam_sessions.get(session_id, {})
        end_time = session.get('end_time', time.time() + 3600)
        
        while time.time() < end_time and active_students.get(roll_no, {}).get('status') == 'active':
            # Wait 60-120 seconds between checks
            await asyncio.sleep(90 + (hash(roll_no) % 30))
            
            # Random chance of detecting cheating (10%)
            if hash(f"{roll_no}{time.time()}") % 10 == 0:
                await self._handle_cheating_detected(roll_no)
    
    async def _handle_cheating_detected(self, roll_no: str):
        """Handle detected cheating incident"""
        try:
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
                student.cheating_count += 1
                
                # Apply penalties
                if student.cheating_count == 1:
                    # First offense: 50% reduction in current marks
                    student.ese_marks = int(student.ese_marks * 0.5)
                    logger.warning(f"First cheating offense for {roll_no}: 50% marks reduction")
                elif student.cheating_count >= 2:
                    # Second offense: terminate exam
                    student.status = "terminated"
                    student.ese_marks = 0
                    active_students[roll_no]['status'] = 'terminated'
                    logger.warning(f"Second cheating offense for {roll_no}: exam terminated")
                
                # Update student data
                await stub.WriteStudentData(
                    pb2.WriteStudentDataRequest(
                        roll_no=roll_no,
                        student_data=student,
                        requester_type="system"
                    )
                )
            
            await channel.close()
            
        except grpc.RpcError as e:
            logger.error(f"Failed to handle cheating for {roll_no}: {e}")

class TeacherServiceServicer(pb2_grpc.TeacherServiceServicer):
    async def StartExamSession(self, request, context):
        """Start a new exam session"""
        duration_minutes = request.duration_minutes
        exam_title = request.exam_title
        
        # Check if there's already an active session
        for session_id, session in exam_sessions.items():
            if session.get('status') == 'active' and time.time() < session.get('end_time', 0):
                return pb2.StartExamSessionResponse(
                    success=False,
                    message="Another exam session is already active.",
                    session_id="",
                    exam_end_time=0
                )
        
        # Create new session
        session_id = str(uuid.uuid4())
        end_time = time.time() + (duration_minutes * 60)
        
        exam_sessions[session_id] = {
            'title': exam_title,
            'start_time': time.time(),
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'status': 'active'
        }
        
        logger.info(f"Started exam session: {exam_title} ({session_id})")
        
        # Start session monitor
        asyncio.create_task(self._monitor_session(session_id))
        
        return pb2.StartExamSessionResponse(
            success=True,
            message=f"Exam session '{exam_title}' started successfully.",
            session_id=session_id,
            exam_end_time=end_time
        )
    
    async def EndExamSession(self, request, context):
        """End an exam session"""
        session_id = request.session_id
        
        if session_id not in exam_sessions:
            return pb2.EndExamSessionResponse(
                success=False,
                message="Session not found."
            )
        
        exam_sessions[session_id]['status'] = 'ended'
        exam_sessions[session_id]['actual_end_time'] = time.time()
        
        # Auto-submit any remaining active students
        await self._auto_submit_remaining_students(session_id)
        
        logger.info(f"Ended exam session: {session_id}")
        
        return pb2.EndExamSessionResponse(
            success=True,
            message="Exam session ended successfully."
        )
    
    async def GetAllStudentMarks(self, request, context):
        """Get all student marks for the current session"""
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            response = await stub.GetAllStudentsData(
                pb2.GetAllStudentsDataRequest(
                    requester_type="teacher"
                )
            )
            
            await channel.close()
            
            return pb2.GetAllStudentMarksResponse(
                success=response.success,
                students=response.students
            )
            
        except grpc.RpcError as e:
            logger.error(f"Failed to get all student marks: {e}")
            return pb2.GetAllStudentMarksResponse(
                success=False,
                students=[]
            )
    
    async def UpdateStudentMarks(self, request, context):
        """Update marks for a specific student"""
        try:
            # Use Ricart-Agrawala for mutual exclusion
            channel_ra = grpc.aio.insecure_channel(RICART_AGRAWALA_URL)
            stub_ra = pb2_grpc.RicartAgrawalaServiceStub(channel_ra)
            
            # Request critical section
            cs_response = await stub_ra.RequestCS(
                pb2.RequestCSRequest(
                    roll_no=f"teacher_{request.roll_no}",
                    lamport_timestamp=int(time.time() * 1000000)
                )
            )
            
            if not cs_response.success:
                await channel_ra.close()
                return pb2.UpdateStudentMarksResponse(
                    success=False,
                    message="Failed to acquire lock for update.",
                    updated_student=pb2.Student()
                )
            
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
                    student.isa_marks = request.isa_marks
                    student.mse_marks = request.mse_marks
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
                        logger.info(f"Updated marks for {request.roll_no} by {request.updated_by}")
                        return pb2.UpdateStudentMarksResponse(
                            success=True,
                            message="Marks updated successfully.",
                            updated_student=write_response.updated_student
                        )
                else:
                    await channel_cs.close()
                    return pb2.UpdateStudentMarksResponse(
                        success=False,
                        message="Student not found.",
                        updated_student=pb2.Student()
                    )
            
            finally:
                # Release critical section
                await stub_ra.ReleaseCS(
                    pb2.ReleaseCSRequest(
                        roll_no=f"teacher_{request.roll_no}",
                        lamport_timestamp=int(time.time() * 1000000)
                    )
                )
                await channel_ra.close()
            
        except grpc.RpcError as e:
            logger.error(f"Failed to update marks for {request.roll_no}: {e}")
            return pb2.UpdateStudentMarksResponse(
                success=False,
                message="System error during update.",
                updated_student=pb2.Student()
            )
    
    async def GetExamResults(self, request, context):
        """Get comprehensive exam results with statistics"""
        try:
            channel = grpc.aio.insecure_channel(CONSISTENCY_SERVICE_URL)
            stub = pb2_grpc.ConsistencyServiceStub(channel)
            
            response = await stub.GetAllStudentsData(
                pb2.GetAllStudentsDataRequest(
                    requester_type="teacher"
                )
            )
            
            await channel.close()
            
            if response.success:
                # Calculate statistics
                students = response.students
                total_students = len(students)
                completed_students = len([s for s in students if s.status == "submitted"])
                cheating_incidents = sum(s.cheating_count for s in students)
                
                if total_students > 0:
                    average_score = sum(s.ese_marks for s in students) / total_students
                    passed_students = len([s for s in students if s.ese_marks >= 40])
                else:
                    average_score = 0
                    passed_students = 0
                
                statistics = pb2.ExamStatistics(
                    total_students=total_students,
                    completed_students=completed_students,
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
            
        except grpc.RpcError as e:
            logger.error(f"Failed to get exam results: {e}")
            return pb2.GetExamResultsResponse(
                success=False,
                students=[],
                statistics=pb2.ExamStatistics()
            )
    
    async def _monitor_session(self, session_id: str):
        """Monitor exam session and auto-end when time expires"""
        session = exam_sessions.get(session_id, {})
        end_time = session.get('end_time', time.time())
        
        while time.time() < end_time:
            await asyncio.sleep(10)  # Check every 10 seconds
        
        # Auto-end session
        if exam_sessions.get(session_id, {}).get('status') == 'active':
            exam_sessions[session_id]['status'] = 'ended'
            exam_sessions[session_id]['actual_end_time'] = time.time()
            await self._auto_submit_remaining_students(session_id)
            logger.info(f"Auto-ended exam session: {session_id}")
    
    async def _auto_submit_remaining_students(self, session_id: str):
        """Auto-submit exams for students who haven't submitted"""
        remaining_students = [
            roll_no for roll_no, data in active_students.items()
            if data.get('session_id') == session_id and data.get('status') == 'active'
        ]
        
        for roll_no in remaining_students:
            # Create empty submission
            empty_answers = []  # No answers provided
            
            submit_request = pb2.SubmitExamRequest(
                roll_no=roll_no,
                session_id=session_id,
                answers=empty_answers,
                submit_type="auto",
                priority=1
            )
            
            # Process auto-submission
            try:
                channel = grpc.aio.insecure_channel(LOAD_BALANCER_URL)
                stub = pb2_grpc.LoadBalancerServiceStub(channel)
                
                await stub.RouteSubmission(
                    pb2.RouteSubmissionRequest(
                        submission=submit_request,
                        current_load=0  # Low priority for auto-submissions
                    )
                )
                
                await channel.close()
                
                # Update student status
                active_students[roll_no]['status'] = 'auto_submitted'
                await self._update_student_score(roll_no, 0)  # Zero score for auto-submission
                
                logger.info(f"Auto-submitted exam for {roll_no}")
                
            except grpc.RpcError as e:
                logger.error(f"Failed to auto-submit for {roll_no}: {e}")

class AdminServiceServicer(pb2_grpc.AdminServiceServicer):
    def __init__(self):
        self.system_logs = []
        self.max_logs = 1000
    
    async def GetSystemLogs(self, request, context):
        """Get recent system logs"""
        last_n = min(request.last_n_lines or 50, self.max_logs)
        service_filter = request.service_name
        
        filtered_logs = self.system_logs
        if service_filter:
            filtered_logs = [log for log in self.system_logs if service_filter.lower() in log.lower()]
        
        recent_logs = filtered_logs[-last_n:] if filtered_logs else []
        
        return pb2.GetSystemLogsResponse(
            log_lines=recent_logs,
            timestamp=int(time.time())
        )
    
    async def GetServerMetrics(self, request, context):
        """Get current server metrics"""
        active_count = len([s for s in active_students.values() if s.get('status') == 'active'])
        completed_count = len([s for s in active_students.values() if s.get('status') in ['submitted', 'auto_submitted']])
        
        return pb2.GetServerMetricsResponse(
            active_students=active_count,
            completed_submissions=completed_count,
            pending_requests=0,  # Would need to implement request queue tracking
            cpu_usage=0.0,  # Would need system monitoring
            memory_usage=0.0  # Would need system monitoring
        )
    
    async def GetActiveConnections(self, request, context):
        """Get active client connections"""
        connections = []
        
        for roll_no, data in active_students.items():
            connections.append(
                pb2.ConnectionInfo(
                    client_id=roll_no,
                    connection_type="student",
                    connected_since=int(data.get('start_time', time.time())),
                    status=data.get('status', 'unknown')
                )
            )
        
        return pb2.GetActiveConnectionsResponse(
            connections=connections
        )
    
    def add_log(self, message: str):
        """Add a log message to the system logs"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        
        self.system_logs.append(log_entry)
        
        # Keep only the most recent logs
        if len(self.system_logs) > self.max_logs:
            self.system_logs = self.system_logs[-self.max_logs:]

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
    
    logger.info(f"Starting Main Server on {listen_addr}")
    admin_service.add_log(f"Main Server started on port {MAIN_SERVER_PORT}")
    
    # Start server
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down Main Server...")
        admin_service.add_log("Main Server shutting down")
        await server.stop(5)

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nMain Server stopped.")
        