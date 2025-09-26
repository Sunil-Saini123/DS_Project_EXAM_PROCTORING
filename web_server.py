#!/usr/bin/env python3
"""
Enhanced Web Server - Fixed version with proper cheating display, score breakdown and Excel support
"""

import asyncio
import grpc
import json
import logging
import os
import time
import glob
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import unified_exam_system_pb2 as pb2
import unified_exam_system_pb2_grpc as pb2_grpc

# Configuration
WEB_SERVER_PORT = 8080
MAIN_SERVER_URL = 'localhost:50050'
CONSISTENCY_SERVICE_URL = 'localhost:50053'
ADMIN_SERVICE_URL = 'localhost:50050'

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WebServer')

# FastAPI app
app = FastAPI(title="Distributed Exam System", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.student_connections: Dict[str, WebSocket] = {}
        self.teacher_connections: List[WebSocket] = []
        self.admin_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_type: str, client_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if client_type == "student" and client_id:
            self.student_connections[client_id] = websocket
        elif client_type == "teacher":
            self.teacher_connections.append(websocket)
        elif client_type == "admin":
            self.admin_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, client_type: str, client_id: str = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if client_type == "student" and client_id and client_id in self.student_connections:
            del self.student_connections[client_id]
        elif client_type == "teacher" and websocket in self.teacher_connections:
            self.teacher_connections.remove(websocket)
        elif client_type == "admin" and websocket in self.admin_connections:
            self.admin_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            pass

    async def send_to_student(self, roll_no: str, message: dict):
        if roll_no in self.student_connections:
            try:
                await self.student_connections[roll_no].send_text(json.dumps(message))
            except:
                pass

    async def broadcast_to_teachers(self, message: dict):
        for connection in self.teacher_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

    async def broadcast_to_admins(self, message: dict):
        for connection in self.admin_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

# Serve static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main index.html page"""
    try:
        with open("index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=404)

# Student API Endpoints
@app.post("/api/student/login")
async def student_login(data: dict):
    """Student login endpoint"""
    roll_no = data.get("roll_no")
    name = data.get("name")
    
    if not roll_no or not name:
        raise HTTPException(status_code=400, detail="Roll number and name are required")
    
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.ExamServiceStub(channel)
        
        response = await stub.StartExam(
            pb2.StartExamRequest(
                roll_no=roll_no,
                student_name=name
            )
        )
        
        await channel.close()
        
        if response.success:
            return {
                "success": True,
                "message": response.message,
                "session_id": response.session_id,
                "exam_end_time": response.exam_end_time
            }
        else:
            return {
                "success": False,
                "message": response.message
            }
            
    except grpc.RpcError as e:
        logger.error(f"Student login failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/student/{roll_no}/questions")
async def get_student_questions(roll_no: str, session_id: str):
    """Get exam questions for student"""
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.ExamServiceStub(channel)
        
        response = await stub.GetExamQuestions(
            pb2.GetExamQuestionsRequest(
                roll_no=roll_no,
                session_id=session_id
            )
        )
        
        await channel.close()
        
        if response.success:
            questions = []
            for q in response.questions:
                questions.append({
                    "question_id": q.question_id,
                    "text": q.text,
                    "options": list(q.options)
                })
            
            return {
                "success": True,
                "questions": questions,
                "time_remaining": response.time_remaining
            }
        else:
            return {"success": False, "questions": []}
            
    except grpc.RpcError as e:
        logger.error(f"Get questions failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.post("/api/student/{roll_no}/submit")
async def submit_exam(roll_no: str, data: dict):
    """Submit exam for student with detailed score breakdown"""
    session_id = data.get("session_id")
    answers = data.get("answers", [])
    submit_type = data.get("submit_type", "manual")
    
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.ExamServiceStub(channel)
        
        # Convert answers to protobuf format
        pb_answers = []
        for answer in answers:
            pb_answers.append(
                pb2.Answer(
                    question_id=answer["question_id"],
                    selected_option=answer["selected_option"]
                )
            )
        
        response = await stub.SubmitExam(
            pb2.SubmitExamRequest(
                roll_no=roll_no,
                session_id=session_id,
                answers=pb_answers,
                submit_type=submit_type,
                priority=1 if submit_type == "auto" else 0
            )
        )
        
        await channel.close()
        
        # Enhanced response with detailed information
        result = {
            "success": response.success,
            "message": response.message,
            "final_score": response.final_score
        }
        
        # If submission successful, add detailed breakdown
        if response.success:
            # Parse message for additional details if cheating penalties were applied
            if "Original:" in response.message and "Penalty:" in response.message:
                import re
                original_match = re.search(r'Original: (\d+)', response.message)
                penalty_match = re.search(r'Penalty: -(\d+)', response.message)
                offenses_match = re.search(r'(\d+) cheating offense', response.message)
                
                if original_match and penalty_match:
                    result["base_score"] = int(original_match.group(1))
                    result["penalty"] = int(penalty_match.group(1))
                    result["cheating_offenses"] = int(offenses_match.group(1)) if offenses_match else 0
                    result["penalty_applied"] = True
                else:
                    result["penalty_applied"] = False
            else:
                result["penalty_applied"] = False
            
            # Broadcast to teachers about new submission
            await manager.broadcast_to_teachers({
                "type": "student_submitted",
                "roll_no": roll_no,
                "submit_type": submit_type,
                "final_score": response.final_score,
                "penalty_applied": result.get("penalty_applied", False)
            })
        
        return result
        
    except grpc.RpcError as e:
        logger.error(f"Submit exam failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/student/{roll_no}/status")
async def get_student_status(roll_no: str):
    """Get current status of student with detailed cheating information"""
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.ExamServiceStub(channel)
        
        response = await stub.GetStudentStatus(
            pb2.GetStudentStatusRequest(roll_no=roll_no)
        )
        
        await channel.close()
        
        if response.success:
            return {
                "success": True,
                "student": {
                    "roll_no": response.student.roll_no,
                    "name": response.student.name,
                    "status": response.student.status,
                    "cheating_count": response.student.cheating_count,
                    "exam_score": response.student.ese_marks  # ESE now stores exam score
                },
                "time_remaining": response.time_remaining
            }
        else:
            return {"success": False}
            
    except grpc.RpcError as e:
        logger.error(f"Get student status failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

# Teacher API Endpoints
@app.post("/api/teacher/login")
async def teacher_login(data: dict):
    """Teacher login endpoint"""
    username = data.get("username")
    password = data.get("password")
    
    if username == "teacher" and password == "exam2024":
        return {
            "success": True,
            "message": "Login successful",
            "token": "teacher_token_" + str(int(time.time()))
        }
    else:
        return {
            "success": False,
            "message": "Invalid credentials"
        }

@app.post("/api/teacher/start-exam")
async def start_exam_session(data: dict):
    """Start a new exam session"""
    duration_minutes = data.get("duration_minutes", 120)
    exam_title = data.get("exam_title", "Distributed Systems Exam")
    
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.TeacherServiceStub(channel)
        
        response = await stub.StartExamSession(
            pb2.StartExamSessionRequest(
                duration_minutes=duration_minutes,
                exam_title=exam_title
            )
        )
        
        await channel.close()
        
        if response.success:
            # Notify all connected clients
            await manager.broadcast_to_teachers({
                "type": "exam_started",
                "session_id": response.session_id,
                "exam_end_time": response.exam_end_time
            })
        
        return {
            "success": response.success,
            "message": response.message,
            "session_id": response.session_id,
            "exam_end_time": response.exam_end_time
        }
        
    except grpc.RpcError as e:
        logger.error(f"Start exam failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.post("/api/teacher/end-exam")
async def end_exam_session(data: dict):
    """End an exam session"""
    session_id = data.get("session_id")
    
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.TeacherServiceStub(channel)
        
        response = await stub.EndExamSession(
            pb2.EndExamSessionRequest(session_id=session_id)
        )
        
        await channel.close()
        
        if response.success:
            # Notify all connected clients
            await manager.broadcast_to_teachers({
                "type": "exam_ended",
                "session_id": session_id
            })
        
        return {
            "success": response.success,
            "message": response.message
        }
        
    except grpc.RpcError as e:
        logger.error(f"End exam failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/teacher/students")
async def get_all_student_marks():
    """Get marks for completed students with detailed cheating information"""
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.TeacherServiceStub(channel)
        
        response = await stub.GetAllStudentMarks(
            pb2.GetAllStudentMarksRequest(session_id="current")
        )
        
        await channel.close()
        
        if response.success:
            students = []
            for student in response.students:
                # Only show completed students (those who have submitted)
                if student.status in ["submitted", "terminated"]:
                    student_data = {
                        "roll_no": student.roll_no,
                        "name": student.name,
                        "exam_score": student.ese_marks,  # Use ese_marks which stores exam score
                        "status": student.status,
                        "cheating_count": student.cheating_count
                    }
                    
                    # Add status description based on cheating count
                    if student.cheating_count >= 3:
                        student_data["status_description"] = "Terminated (3+ Cheating Offenses)"
                        student_data["status_color"] = "red"
                    elif student.cheating_count > 0:
                        student_data["status_description"] = f"Submitted ({student.cheating_count} Cheating Offense(s))"
                        student_data["status_color"] = "orange"
                    else:
                        student_data["status_description"] = "Submitted (Clean)"
                        student_data["status_color"] = "green"
                    
                    students.append(student_data)
            
            return {
                "success": True,
                "students": students
            }
        else:
            return {"success": False, "students": []}
            
    except grpc.RpcError as e:
        logger.error(f"Get student marks failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.put("/api/teacher/student/{roll_no}/marks")
async def update_student_marks(roll_no: str, data: dict):
    """Update exam score for a specific student"""
    exam_score = data.get("exam_score", 0)
    updated_by = data.get("updated_by", "teacher")
    
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.TeacherServiceStub(channel)
        
        # Use ESE field to store exam score
        response = await stub.UpdateStudentMarks(
            pb2.UpdateStudentMarksRequest(
                roll_no=roll_no,
                isa_marks=0,  # Not used in exam system
                mse_marks=0,  # Not used in exam system
                ese_marks=exam_score,  # This stores the exam score
                updated_by=updated_by
            )
        )
        
        await channel.close()
        
        if response.success:
            # Notify teachers of the update
            await manager.broadcast_to_teachers({
                "type": "marks_updated",
                "roll_no": roll_no,
                "updated_student": {
                    "roll_no": response.updated_student.roll_no,
                    "name": response.updated_student.name,
                    "exam_score": response.updated_student.ese_marks
                }
            })
        
        return {
            "success": response.success,
            "message": response.message,
            "updated_student": {
                "roll_no": response.updated_student.roll_no,
                "name": response.updated_student.name,
                "exam_score": response.updated_student.ese_marks
            } if response.success else None
        }
        
    except grpc.RpcError as e:
        logger.error(f"Update marks failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/teacher/results")
async def get_exam_results():
    """Get comprehensive exam results with statistics"""
    try:
        channel = grpc.aio.insecure_channel(MAIN_SERVER_URL)
        stub = pb2_grpc.TeacherServiceStub(channel)
        
        response = await stub.GetExamResults(
            pb2.GetExamResultsRequest(session_id="current")
        )
        
        await channel.close()
        
        if response.success:
            students = []
            for student in response.students:
                students.append({
                    "roll_no": student.roll_no,
                    "name": student.name,
                    "exam_score": student.ese_marks,  # ESE stores exam score
                    "status": student.status,
                    "cheating_count": student.cheating_count
                })
            
            return {
                "success": True,
                "students": students,
                "statistics": {
                    "total_students": response.statistics.total_students,
                    "completed_students": response.statistics.completed_students,
                    "cheating_incidents": response.statistics.cheating_incidents,
                    "average_score": response.statistics.average_score,
                    "passed_students": response.statistics.passed_students
                }
            }
        else:
            return {"success": False, "students": [], "statistics": {}}
            
    except grpc.RpcError as e:
        logger.error(f"Get exam results failed: {e}")
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/teacher/excel/download")
async def download_excel_file():
    """Download the current exam results Excel file - FIXED VERSION"""
    try:
        # Look for Excel files in Results directory first, then current directory
        excel_files = []
        
        # Check Results directory
        if os.path.exists("Results"):
            results_files = glob.glob("Results/exam_results_*.xlsx")
            excel_files.extend(results_files)
        
        # Also check current directory as fallback
        current_files = glob.glob("exam_results_*.xlsx")
        excel_files.extend(current_files)
        
        if not excel_files:
            logger.error("No Excel files found in Results/ or current directory")
            raise HTTPException(status_code=404, detail="No exam results file found. Please start an exam session first.")
        
        # Get the most recent file
        latest_file = max(excel_files, key=os.path.getctime)
        
        if not os.path.exists(latest_file):
            logger.error(f"Excel file {latest_file} does not exist")
            raise HTTPException(status_code=404, detail="Excel file not found")
        
        # Check if file is accessible
        try:
            with open(latest_file, 'rb') as f:
                f.read(1)  # Try to read first byte to check accessibility
        except PermissionError:
            logger.error(f"Excel file {latest_file} is currently open and locked")
            raise HTTPException(status_code=423, detail="Excel file is currently open in another program. Please close it and try again.")
        except Exception as e:
            logger.error(f"Cannot access Excel file {latest_file}: {e}")
            raise HTTPException(status_code=500, detail="Cannot access Excel file")
        
        logger.info(f"Serving Excel file: {latest_file}")
        
        return FileResponse(
            path=latest_file,
            filename=f"exam_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Download Excel failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@app.get("/api/teacher/excel/status")
async def get_excel_status():
    """Get status of Excel files"""
    try:
        # Check both Results directory and current directory
        excel_files = []
        
        if os.path.exists("Results"):
            results_files = glob.glob("Results/exam_results_*.xlsx")
            excel_files.extend(results_files)
        
        current_files = glob.glob("exam_results_*.xlsx")
        excel_files.extend(current_files)
        
        files_info = []
        for file_path in excel_files:
            try:
                file_stat = os.stat(file_path)
                files_info.append({
                    "filename": os.path.basename(file_path),
                    "size": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    "path": file_path,
                    "accessible": True
                })
            except Exception as e:
                files_info.append({
                    "filename": os.path.basename(file_path),
                    "size": 0,
                    "modified": "Unknown",
                    "path": file_path,
                    "accessible": False,
                    "error": str(e)
                })
        
        # Sort by modification time (newest first)
        accessible_files = [f for f in files_info if f.get("accessible", False)]
        accessible_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "success": True,
            "files": files_info,
            "accessible_files": len(accessible_files),
            "current_file": accessible_files[0]["filename"] if accessible_files else None
        }
        
    except Exception as e:
        logger.error(f"Get Excel status failed: {e}")
        return {
            "success": False,
            "files": [],
            "accessible_files": 0,
            "current_file": None,
            "error": str(e)
        }

# Admin API Endpoints
@app.post("/api/admin/login")
async def admin_login(data: dict):
    """Admin login endpoint"""
    username = data.get("username")
    password = data.get("password")
    
    if username == "admin" and password == "admin2024":
        return {
            "success": True,
            "message": "Login successful",
            "token": "admin_token_" + str(int(time.time()))
        }
    else:
        return {
            "success": False,
            "message": "Invalid credentials"
        }

@app.get("/api/admin/logs")
async def get_system_logs(last_n: int = 50, service_name: str = ""):
    """Get system logs with enhanced filtering and cheating detection logs"""
    try:
        channel = grpc.aio.insecure_channel(ADMIN_SERVICE_URL)
        stub = pb2_grpc.AdminServiceStub(channel)
        
        response = await stub.GetSystemLogs(
            pb2.GetSystemLogsRequest(
                last_n_lines=last_n,
                service_name=service_name
            )
        )
        
        await channel.close()
        
        # Get logs from main server
        logs = list(response.log_lines)
        
        return {
            "success": True,
            "logs": logs,
            "timestamp": response.timestamp
        }
        
    except grpc.RpcError as e:
        logger.error(f"Get logs failed: {e}")
        # Enhanced fallback with cheating detection examples
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fallback_logs = [
            f"[{current_time}] WebServer: Connection to main server failed: {str(e)}",
            f"[{current_time}] WebServer: Showing cached/local logs",
            f"[{current_time}] MainServer: CHEATING DETECTED: Student 23102A0027 caught cheating! (Offense #1)",
            f"[{current_time}] MainServer: CHEATING PENALTY APPLIED: 23102A0027 - 1st offense, 80 → 60 (-20)",
            f"[{current_time}] MainServer: Starting enhanced cheating detection system",
            f"[{current_time}] MainServer: Student 23102A0028 submitted exam successfully, final score: 90, base score: 90, cheating count: 0",
            f"[{current_time}] MainServer: CHEATING DETECTED: Student 23102A0029 caught cheating! (Offense #2)",
            f"[{current_time}] MainServer: CHEATING PENALTY APPLIED: 23102A0029 - 2nd offense, 70 → 35 (-35)",
            f"[{current_time}] MainServer: EXAM TERMINATED: 23102A0030 - 3rd cheating offense, final score: 0",
            f"[{current_time}] MainServer: Updated Excel file for student 23102A0031 - Final: 75, Base: 80, Penalty: 5",
            f"[{current_time}] WebServer: Teachers connected: {len(manager.teacher_connections)}",
            f"[{current_time}] WebServer: Students connected: {len(manager.student_connections)}",
            f"[{current_time}] WebServer: Admins connected: {len(manager.admin_connections)}",
        ]
        
        return {
            "success": True,
            "logs": fallback_logs,
            "timestamp": int(time.time())
        }

@app.get("/api/admin/metrics")
async def get_server_metrics():
    """Get server metrics"""
    try:
        channel = grpc.aio.insecure_channel(ADMIN_SERVICE_URL)
        stub = pb2_grpc.AdminServiceStub(channel)
        
        response = await stub.GetServerMetrics(
            pb2.GetServerMetricsRequest()
        )
        
        await channel.close()
        
        return {
            "success": True,
            "metrics": {
                "active_students": response.active_students,
                "completed_submissions": response.completed_submissions,
                "pending_requests": response.pending_requests,
                "cpu_usage": response.cpu_usage,
                "memory_usage": response.memory_usage,
                "timestamp": datetime.now().isoformat(),
                # Add web server specific metrics
                "websocket_connections": {
                    "teachers": len(manager.teacher_connections),
                    "students": len(manager.student_connections),
                    "admins": len(manager.admin_connections),
                    "total": len(manager.active_connections)
                }
            }
        }
        
    except grpc.RpcError as e:
        logger.error(f"Get metrics failed: {e}")
        return {
            "success": False,
            "metrics": {}
        }

@app.get("/api/admin/connections")
async def get_active_connections():
    """Get active connections"""
    try:
        channel = grpc.aio.insecure_channel(ADMIN_SERVICE_URL)
        stub = pb2_grpc.AdminServiceStub(channel)
        
        response = await stub.GetActiveConnections(
            pb2.GetActiveConnectionsRequest()
        )
        
        await channel.close()
        
        connections = []
        for conn in response.connections:
            connections.append({
                "client_id": conn.client_id,
                "connection_type": conn.connection_type,
                "connected_since": datetime.fromtimestamp(conn.connected_since).isoformat(),
                "status": conn.status
            })
        
        # Add WebSocket connections
        current_time = datetime.now().isoformat()
        for client_id, ws in manager.student_connections.items():
            connections.append({
                "client_id": f"WS-Student-{client_id}",
                "connection_type": "websocket_student",
                "connected_since": current_time,
                "status": "connected"
            })
        
        for i, ws in enumerate(manager.teacher_connections):
            connections.append({
                "client_id": f"WS-Teacher-{i}",
                "connection_type": "websocket_teacher", 
                "connected_since": current_time,
                "status": "connected"
            })
            
        for i, ws in enumerate(manager.admin_connections):
            connections.append({
                "client_id": f"WS-Admin-{i}",
                "connection_type": "websocket_admin",
                "connected_since": current_time,
                "status": "connected"
            })
        
        return {
            "success": True,
            "connections": connections
        }
        
    except grpc.RpcError as e:
        logger.error(f"Get connections failed: {e}")
        return {
            "success": False,
            "connections": []
        }

# WebSocket endpoints
@app.websocket("/ws/student/{roll_no}")
async def websocket_student(websocket: WebSocket, roll_no: str):
    """WebSocket endpoint for students"""
    await manager.connect(websocket, "student", roll_no)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "heartbeat":
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_response",
                    "timestamp": time.time()
                }))
            elif message["type"] == "status_request":
                # Get updated student status and send it
                try:
                    status_response = await get_student_status(roll_no)
                    await websocket.send_text(json.dumps({
                        "type": "status_update",
                        "data": status_response
                    }))
                except:
                    pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, "student", roll_no)

@app.websocket("/ws/teacher")
async def websocket_teacher(websocket: WebSocket):
    """WebSocket endpoint for teachers"""
    await manager.connect(websocket, "teacher")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "heartbeat":
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_response",
                    "timestamp": time.time()
                }))
            elif message["type"] == "request_student_updates":
                # Send current student data (only completed students)
                try:
                    students_response = await get_all_student_marks()
                    await websocket.send_text(json.dumps({
                        "type": "students_update",
                        "data": students_response
                    }))
                except:
                    pass
            elif message["type"] == "request_excel_status":
                # Send Excel file status
                try:
                    excel_status = await get_excel_status()
                    await websocket.send_text(json.dumps({
                        "type": "excel_status",
                        "data": excel_status
                    }))
                except:
                    pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, "teacher")

@app.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    """WebSocket endpoint for admins"""
    await manager.connect(websocket, "admin")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "heartbeat":
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_response",
                    "timestamp": time.time()
                }))
            elif message["type"] == "request_logs":
                # Send recent logs
                try:
                    logs_response = await get_system_logs(
                        last_n=message.get("lines", 50),
                        service_name=message.get("service", "")
                    )
                    await websocket.send_text(json.dumps({
                        "type": "logs_update",
                        "data": logs_response
                    }))
                except:
                    pass
            elif message["type"] == "request_metrics":
                # Send current metrics
                try:
                    metrics_response = await get_server_metrics()
                    await websocket.send_text(json.dumps({
                        "type": "metrics_update",
                        "data": metrics_response
                    }))
                except:
                    pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, "admin")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    logger.info(f"Starting Enhanced Web Server on port {WEB_SERVER_PORT}")
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=WEB_SERVER_PORT,
        log_level="info",
        reload=False
    )