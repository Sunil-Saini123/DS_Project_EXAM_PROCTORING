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
- **Edit Marks**: Click "Edit Marks" → Click on ISA/MSE/ESE cells → Edit values → "Save Changes"
- **End Exam**: Force end exam session

### Admin Tab
- **Login**: Username: `admin`, Password: `admin2024`
- **Metrics**: Live system performance indicators
- **Logs**: Real-time system logs with service filtering
- **Connections**: Active client connection monitoring

## 🧪 Testing Scenarios

### 1. Normal Exam Flow
```bash
# Terminal 1-5: Start all services (as above)
# Browser: 
# 1. Go to Student tab
# 2. Login with roll number "23102A0027" and name "Test Student"
# 3. Answer questions
# 4. Submit manually or wait for auto-submission
```

### 2. Teacher Operations
```bash
# Browser:
# 1. Go to Teacher tab
# 2. Login (teacher/exam2024)
# 3. Start exam with 2-minute duration
# 4. Switch to Student tab in new browser window/incognito
# 5. Login as student and take exam
# 6. Return to Teacher tab to see live updates
# 7. Use "Edit Marks" to modify student scores
```

### 3. Concurrent Mark Editing
```bash
# Open two teacher sessions in different browser windows
# Try to edit the same student's marks simultaneously
# The system uses Ricart-Agrawala locks to prevent conflicts
```

### 4. Load Balancing Test
```bash
# Simulate high load by having multiple students submit simultaneously
# The system will route requests to backup server when load exceeds threshold
```

### 5. Cheating Detection
```bash
# The system randomly detects "cheating" for demonstration
# First offense: 50% mark reduction
# Second offense: Exam termination
```

## 🔧 Configuration

### Server Ports
- **Web Server**: 8080
- **Main Server**: 50050
- **Consistency Service**: 50053
- **Ricart-Agrawala Service**: 50052
- **Load Balancer**: 50055
- **Backup Server**: 50056

### Exam Settings
- **Default Duration**: 2 minutes (configurable in teacher interface)
- **Questions**: 10 multiple-choice questions (hardcoded)
- **Scoring**: 10 points per correct answer
- **Auto-submission**: When time expires or on second cheating offense

### Data Storage
- **Primary Data**: `exam_data/` directory
- **Backup Data**: `exam_data_backup/` directory
- **Sharding**: 4 shards based on roll number hash
- **Replication**: Each shard has primary and backup copies

## 🔍 Architecture Details

### gRPC Services
1. **ExamService**: Handles student exam flow
2. **TeacherService**: Manages teacher operations
3. **ConsistencyService**: Ensures data consistency
4. **LoadBalancerService**: Routes and balances requests
5. **RicartAgrawalaService**: Provides mutual exclusion
6. **AdminService**: System monitoring and logging

### Data Consistency
- **Sharding**: Student data distributed across 4 shards
- **Replication**: Primary and backup copies for fault tolerance
- **Locking**: Distributed locks for concurrent access control
- **Transactions**: Begin/end transaction support for complex operations

### Load Balancing
- **Threshold**: Max 15 concurrent requests on primary server
- **Failover**: Automatic routing to backup server
- **Health Monitoring**: Periodic backup server health checks
- **Request Migration**: Bulk request migration during high load

### Mutual Exclusion
- **Algorithm**: Ricart-Agrawala distributed mutual exclusion
- **Resource Types**: Student data, global reads, mark updates
- **Priority**: Timestamp-based request ordering
- **Deadlock Prevention**: Timeout mechanisms and proper resource ordering

## 🐛 Troubleshooting

### Common Issues

#### Services Won't Start
```bash
# Check if ports are in use
netstat -tulpn | grep :50050
netstat -tulpn | grep :8080

# Kill existing processes if needed
pkill -f "python.*main_server"
pkill -f "python.*web_server"
```

#### gRPC Import Errors
```bash
# Regenerate protobuf files
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. --proto_path=. unified_exam_system.proto
```

#### Data Consistency Issues
```bash
# Clear and reinitialize data
rm -rf exam_data exam_data_backup
mkdir -p exam_data exam_data_backup

# Restart consistency service
python consistency_service.py
```

#### WebSocket Connection Issues
```bash
# Check if web server is running
curl http://localhost:8080/health

# Browser console errors - refresh page and check browser developer tools
```

#### Load Balancer Not Working
```bash
# Verify all services are running
ps aux | grep python

# Check service logs for errors
# Services should start in order: Ricart-Agrawala → Consistency → Load Balancer → Main → Web
```

### Debugging Tips

1. **Check Service Order**: Services must start in the specified order
2. **Port Conflicts**: Ensure no other applications are using the required ports
3. **Log Analysis**: Each service logs important events - check console outputs
4. **Browser Developer Tools**: Use F12 to check for JavaScript errors
5. **Network Issues**: Verify all services can communicate with each other

## 📊 Monitoring and Metrics

### System Metrics (Admin Tab)
- **Active Students**: Number of students currently taking exams
- **Completed Submissions**: Total submitted exams
- **Pending Requests**: Requests waiting in queues
- **System Load**: Overall system load indicator

### Service Health Indicators
- **Green**: Service running normally
- **Yellow**: Service experiencing issues
- **Red**: Service unavailable or failed

### Performance Monitoring
- **Request Latency**: Time taken for request processing
- **Queue Lengths**: Number of waiting requests
- **Critical Section Usage**: Active distributed locks
- **WebSocket Connections**: Real-time connection count

## 🔐 Security Considerations

### Current Implementation
- **Simple Authentication**: Username/password for teachers and admins
- **No Encryption**: Communications are not encrypted (development only)
- **No Session Management**: Basic token-based sessions
- **Local Storage**: Data stored locally without encryption

### Production Recommendations
- **HTTPS**: Enable SSL/TLS for all communications
- **JWT Tokens**: Implement proper JWT-based authentication
- **Database Security**: Use encrypted database connections
- **Rate Limiting**: Implement request rate limiting
- **Input Validation**: Add comprehensive input sanitization
- **Audit Logging**: Log all administrative actions

## 🎯 System Testing

### Load Testing
```bash
# Simulate multiple concurrent students
for i in {1..10}; do
    curl -X POST http://localhost:8080/api/student/login \
         -H "Content-Type: application/json" \
         -d "{\"roll_no\":\"STUDENT${i}\",\"name\":\"Test Student ${i}\"}" &
done
```

### Stress Testing
```bash
# Test distributed locking under high concurrency
# Multiple teacher sessions trying to update marks simultaneously
# System should maintain consistency without data corruption
```

### Fault Tolerance Testing
```bash
# Stop services one by one and observe system behavior
# Test backup server activation
# Test data recovery from backup shards
```

## 📈 Performance Optimization

### Recommended Optimizations
1. **Connection Pooling**: Implement gRPC connection pooling
2. **Caching**: Add Redis for frequently accessed data
3. **Database**: Replace file storage with proper database
4. **Load Balancing**: Add multiple backup servers
5. **CDN**: Use CDN for static assets
6. **Compression**: Enable gRPC compression

### Scaling Considerations
- **Horizontal Scaling**: Add more service instances
- **Database Sharding**: Increase number of data shards
- **Geographic Distribution**: Deploy across multiple regions
- **Microservices**: Further decompose services for better scaling

## 🔄 System Workflow

### Student Workflow
1. **Login** → Validate credentials → Create session
2. **Start Exam** → Load questions → Start timer
3. **Answer Questions** → Save answers locally → Real-time validation
4. **Submit** → Process through load balancer → Update scores
5. **Results** → Display final scores → Close session

### Teacher Workflow
1. **Login** → Authenticate → Access dashboard
2. **Start Exam** → Configure settings → Notify students
3. **Monitor** → Real-time student tracking → Handle issues
4. **Edit Marks** → Acquire locks → Update database → Release locks
5. **End Exam** → Force submissions → Generate reports

### Admin Workflow
1. **Login** → Authenticate → Access monitoring
2. **Monitor** → View metrics → Check logs
3. **Debug** → Analyze connections → Review performance
4. **Maintain** → System health checks → Issue resolution

## 🛡️ Data Consistency Guarantees

### ACID Properties
- **Atomicity**: Mark updates are atomic operations
- **Consistency**: Data remains consistent across shards
- **Isolation**: Concurrent operations don't interfere
- **Durability**: Changes are persisted to backup storage

### Distributed Locking
- **Ricart-Agrawala Algorithm**: Ensures mutual exclusion
- **Deadlock Prevention**: Timeout mechanisms prevent deadlocks
- **Priority Ordering**: Timestamp-based request prioritization
- **Resource Management**: Proper lock acquisition and release

### Replication Strategy
- **Primary-Backup**: Each shard has primary and backup copies
- **Synchronous Replication**: Changes written to both copies
- **Consistency Checks**: Periodic consistency verification
- **Recovery Procedures**: Automatic failover to backup copies

## 📚 Educational Value

This project demonstrates several key distributed systems concepts:

### Distributed Algorithms
- **Ricart-Agrawala**: Distributed mutual exclusion
- **Lamport Clocks**: Logical time ordering
- **Byzantine Fault Tolerance**: Handling node failures

### System Architecture
- **Microservices**: Service decomposition and communication
- **Load Balancing**: Request distribution and failover
- **Data Consistency**: CAP theorem tradeoffs

### Real-world Applications
- **Exam Systems**: Proctored online testing platforms
- **Banking Systems**: Transaction processing with consistency
- **E-commerce**: Inventory management with concurrent updates

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch
3. Follow coding standards
4. Add comprehensive tests
5. Submit pull request

### Code Standards
- **Python**: Follow PEP 8 style guidelines
- **Documentation**: Comprehensive docstrings
- **Testing**: Unit and integration tests
- **Logging**: Structured logging throughout

### Feature Additions
- **New Services**: Follow existing gRPC patterns
- **UI Components**: Use Tailwind CSS classes
- **API Endpoints**: RESTful design principles
- **Database Changes**: Migration scripts required

## 📄 License

This project is provided for educational purposes. See LICENSE file for details.

## 🙋 Support

### Getting Help
1. **Documentation**: Check this README thoroughly
2. **Issues**: Create GitHub issues for bugs
3. **Discussions**: Use GitHub discussions for questions
4. **Email**: Contact maintainers for critical issues

### Common Questions
- **Q**: Can I run this in production?
  **A**: This is an educational project. Production deployment requires security hardening.

- **Q**: How do I add more questions?
  **A**: Modify the `exam_questions` list in `main_server.py`.

- **Q**: Can I use a different database?
  **A**: Yes, modify the `consistency_service.py` to use your preferred database.

- **Q**: How do I increase exam duration?
  **A**: Use the teacher interface to set custom duration when starting an exam.

---

**Built with**: Python, gRPC, FastAPI, WebSockets, Tailwind CSS

**Distributed Systems Concepts**: Consistency, Availability, Partition Tolerance, Mutual Exclusion, Load Balancing, Replication

**Educational Focus**: Practical implementation of theoretical distributed systems concepts