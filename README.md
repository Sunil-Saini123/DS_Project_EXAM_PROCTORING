# Distributed Online Exam System

A comprehensive distributed system implementation for online examinations featuring real-time exam taking, automatic submission, cheating detection, load balancing, data consistency, and mutual exclusion.

## 🎯 Project Overview

This system integrates multiple distributed systems concepts into a unified architecture:

- **Distributed Architecture**: Multiple gRPC services working together
- **Load Balancing**: Automatic request routing with failover to backup servers
- **Data Consistency**: Sharded data with replication and consistency guarantees
- **Mutual Exclusion**: Ricart-Agrawala algorithm for distributed locking
- **Real-time Communication**: WebSocket connections for live updates
- **Web Interface**: Modern three-tab UI for students, teachers, and administrators

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Web Server     │    │  Main Server    │
│  (Students,     │◄──►│  (FastAPI)       │◄──►│  (Coordinator)  │
│   Teachers,     │    │  Port: 8080      │    │  Port: 50050    │
│   Admins)       │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    gRPC Service Layer                           │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ Consistency     │ Load Balancer   │ Ricart-Agrawala             │
│ Service         │ Service         │ Service                     │
│ Port: 50053     │ Port: 50055     │ Port: 50052                 │
│                 │                 │                             │
│ - Data sharding │ - Request       │ - Distributed mutual       │
│ - Replication   │   routing       │   exclusion                 │
│ - Transactions  │ - Failover      │ - Critical sections        │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## 🚀 Features

### For Students
- **Secure Login**: Roll number and name-based authentication
- **Real-time Exam**: Interactive question interface with timer
- **Auto-submission**: Automatic submission when time expires
- **Live Status**: Real-time updates on exam status
- **Cheating Detection**: Automatic monitoring with penalties

### For Teachers
- **Exam Management**: Start/end exam sessions with configurable duration
- **Live Monitoring**: Real-time view of student progress
- **Direct Mark Editing**: Click-to-edit table interface for mark updates
- **Comprehensive Results**: Detailed statistics and student performance
- **Concurrent Safety**: Distributed locks prevent data corruption

### For Administrators
- **System Monitoring**: Live metrics and performance indicators
- **Log Viewing**: Real-time system logs with filtering
- **Connection Tracking**: Monitor active client connections
- **Load Balancing Status**: View request distribution and server health

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (for cloning the repository)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd distributed-exam-system
```

### 2. Install Required Packages
```bash
pip install grpcio grpcio-tools protobuf fastapi uvicorn websockets
```

### 3. Generate gRPC Code
```bash
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. --proto_path=. unified_exam_system.proto
```

This will generate:
- `unified_exam_system_pb2.py` (Protocol buffer messages)
- `unified_exam_system_pb2_grpc.py` (gRPC service stubs)

### 4. Create Required Directories
```bash
mkdir -p exam_data exam_data_backup static
```

## 🚀 Running the System

The system consists of multiple services that must be started in the correct order:

### Step 1: Start the Ricart-Agrawala Service (Terminal 1)
```bash
python ricart_agrawala_service.py
```
Expected output:
```
INFO:RicartAgrawala:Ricart-Agrawala Service initialized
INFO:RicartAgrawala:Starting Ricart-Agrawala Service on [::]:50052
```

### Step 2: Start the Consistency Service (Terminal 2)
```bash
python consistency_service.py
```
Expected output:
```
INFO:ConsistencyService:Initialized 18 students across 4 shards
INFO:ConsistencyService:Loaded 18 students into cache
INFO:ConsistencyService:Starting Consistency Service on [::]:50053
```

### Step 3: Start the Load Balancer Service (Terminal 3)
```bash
python load_balancer_service.py
```
Expected output:
```
INFO:LoadBalancer:Starting Load Balancer Service on [::]:50055
INFO:LoadBalancer:Starting Backup Server on [::]:50056
```

### Step 4: Start the Main Server (Terminal 4)
```bash
python main_server.py
```
Expected output:
```
INFO:MainServer:Starting Main Server on [::]:50050
```

### Step 5: Start the Web Server (Terminal 5)
```bash
python web_server.py
```
Expected output:
```
INFO:WebServer:Starting Web Server on port 8080
INFO:     Uvicorn running on http://0.0.0.0:8080
```

## 🌐 Accessing the System

Open your web browser and navigate to:
```
http://localhost:8080
```

You'll see a modern three-tab interface:

### Student Tab
- **Login**: Use any roll number (e.g., "23102A0027") and your name
- **Exam**: Answer 10 multiple-choice questions
- **Timer**: Countdown shows remaining time
- **Submit**: Manual submission or automatic when time expires

### Teacher Tab
- **Login**: Username: `teacher`, Password: `exam2024`
- **Start Exam**: Configure duration (default: 2 minutes for testing)
- **View Students**: Real-time student progress monitoring
- **Edit Marks**: Click "Edit Marks" → Click on score cells → Edit values → "Save Changes"
- **End Exam**: Force end exam session

### Admin Tab
- **Login**: Username: `admin`, Password: `admin2024`
- **Metrics**: Live system performance indicators
- **Logs**: Real-time system logs with service filtering
- **Connections**: Active client connection monitoring
