# server.py - FastAPI Backend Optimized for Render Deployment
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import psycopg2
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import uuid
from contextlib import asynccontextmanager

# Environment configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

PORT = int(os.getenv('PORT', 8000))

def init_postgres_db():
    """Initialize PostgreSQL database for Render"""
    if not DATABASE_URL:
        print("WARNING: No DATABASE_URL found. Database features will be disabled.")
        return
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Create gait_records table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS gait_records (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    patient_id VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    walking_speed DECIMAL(10,4),
                    step_length DECIMAL(10,4),
                    walking_asymmetry DECIMAL(10,4),
                    double_support_time DECIMAL(10,4),
                    step_count INTEGER,
                    step_cadence DECIMAL(10,4),
                    six_minute_walk_distance DECIMAL(10,4),
                    speed_category VARCHAR(50),
                    asymmetry_alert BOOLEAN DEFAULT FALSE,
                    double_support_alert BOOLEAN DEFAULT FALSE,
                    data_type VARCHAR(20) DEFAULT 'real_time',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_patient_timestamp 
                ON gait_records(patient_id, timestamp DESC)
            """))
            
            # Create medication_changes table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS medication_changes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    patient_id VARCHAR(50) NOT NULL,
                    change_date TIMESTAMP NOT NULL,
                    medication_name VARCHAR(100),
                    old_dosage VARCHAR(50),
                    new_dosage VARCHAR(50),
                    reason TEXT,
                    pharmacist_id VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create patient_thresholds table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS patient_thresholds (
                    patient_id VARCHAR(50) PRIMARY KEY,
                    walking_speed_threshold DECIMAL(10,4) DEFAULT 0.8,
                    asymmetry_threshold DECIMAL(10,4) DEFAULT 10.0,
                    double_support_threshold DECIMAL(10,4) DEFAULT 30.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.commit()
            print("Database tables initialized successfully")
            
    except Exception as e:
        print(f"Database initialization error: {e}")

# Connection manager for WebSocket clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pharmacist_connections: List[WebSocket] = []

    async def connect_patient(self, websocket: WebSocket, patient_id: str):
        await websocket.accept()
        self.active_connections[patient_id] = websocket
        print(f"Patient {patient_id} connected via WebSocket")

    async def connect_pharmacist(self, websocket: WebSocket):
        await websocket.accept()
        self.pharmacist_connections.append(websocket)
        print("Pharmacist connected to alert stream")

    def disconnect_patient(self, patient_id: str):
        if patient_id in self.active_connections:
            del self.active_connections[patient_id]
            print(f"Patient {patient_id} disconnected")

    def disconnect_pharmacist(self, websocket: WebSocket):
        if websocket in self.pharmacist_connections:
            self.pharmacist_connections.remove(websocket)
            print("Pharmacist disconnected from alert stream")

    async def notify_pharmacists(self, message: dict):
        """Notify all connected pharmacists of alerts"""
        if not self.pharmacist_connections:
            return
            
        dead_connections = []
        for connection in self.pharmacist_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Failed to send message to pharmacist: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for dead in dead_connections:
            self.pharmacist_connections.remove(dead)

manager = ConnectionManager()

# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    print("Starting up: Initializing database...")
    init_postgres_db()
    yield
    # Cleanup on shutdown
    print("Shutting down...")

# FastAPI app
app = FastAPI(
    title="Gait Monitoring API", 
    version="1.0.0",
    description="Real-time gait monitoring for MS/Parkinson's patients",
    lifespan=lifespan
)

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def store_gait_data(data: dict):
    """Store gait data in PostgreSQL database"""
    if not DATABASE_URL:
        print("No database connection available")
        return None
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO gait_records (
                    patient_id, timestamp, walking_speed, step_length,
                    walking_asymmetry, double_support_time, step_count,
                    step_cadence, six_minute_walk_distance, speed_category,
                    asymmetry_alert, double_support_alert, data_type
                ) VALUES (
                    :patient_id, :timestamp, :walking_speed, :step_length,
                    :walking_asymmetry, :double_support_time, :step_count,
                    :step_cadence, :six_minute_walk_distance, :speed_category,
                    :asymmetry_alert, :double_support_alert, :data_type
                ) RETURNING id
            """), {
                'patient_id': data.get('patient_id'),
                'timestamp': data.get('timestamp'),
                'walking_speed': data.get('walking_speed'),
                'step_length': data.get('step_length'),
                'walking_asymmetry': data.get('walking_asymmetry'),
                'double_support_time': data.get('double_support_time'),
                'step_count': data.get('step_count'),
                'step_cadence': data.get('step_cadence'),
                'six_minute_walk_distance': data.get('six_minute_walk_distance'),
                'speed_category': data.get('speed_category'),
                'asymmetry_alert': data.get('asymmetry_alert', False),
                'double_support_alert': data.get('double_support_alert', False),
                'data_type': data.get('data_type', 'real_time')
            })
            
            conn.commit()
            record_id = result.fetchone()[0]
            print(f"Stored gait data for patient {data.get('patient_id')}")
            return str(record_id)
            
    except Exception as e:
        print(f"Database error storing gait data: {e}")
        return None

def check_for_alerts(data: dict) -> List[dict]:
    """Check if gait data indicates potential flare"""
    alerts = []
    patient_id = data.get('patient_id')
    
    # Get patient-specific thresholds or use defaults
    thresholds = get_patient_thresholds(patient_id)
    
    # Check for alerts based on thresholds
    if data.get('walking_speed') and data['walking_speed'] < thresholds['speed']:
        alerts.append({
            'type': 'walking_speed_low',
            'message': f'Walking speed below threshold: {data["walking_speed"]:.2f} m/s (threshold: {thresholds["speed"]} m/s)',
            'severity': 'high',
            'patient_id': patient_id,
            'timestamp': data.get('timestamp'),
            'value': data['walking_speed']
        })
    
    if data.get('walking_asymmetry') and data['walking_asymmetry'] > thresholds['asymmetry']:
        alerts.append({
            'type': 'asymmetry_high', 
            'message': f'High gait asymmetry detected: {data["walking_asymmetry"]:.1f}% (threshold: {thresholds["asymmetry"]}%)',
            'severity': 'medium',
            'patient_id': patient_id,
            'timestamp': data.get('timestamp'),
            'value': data['walking_asymmetry']
        })
    
    if data.get('double_support_time') and data['double_support_time'] > thresholds['double_support']:
        alerts.append({
            'type': 'double_support_high',
            'message': f'Increased double support time: {data["double_support_time"]:.1f}% (threshold: {thresholds["double_support"]}%)',
            'severity': 'medium', 
            'patient_id': patient_id,
            'timestamp': data.get('timestamp'),
            'value': data['double_support_time']
        })
    
    return alerts

def get_patient_thresholds(patient_id: str) -> dict:
    """Get patient-specific thresholds or defaults"""
    if not DATABASE_URL:
        return {'speed': 0.8, 'asymmetry': 10.0, 'double_support': 30.0}
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT walking_speed_threshold, asymmetry_threshold, double_support_threshold
                FROM patient_thresholds 
                WHERE patient_id = :patient_id
            """), {'patient_id': patient_id})
            
            row = result.fetchone()
            if row:
                return {
                    'speed': float(row[0]),
                    'asymmetry': float(row[1]),
                    'double_support': float(row[2])
                }
            else:
                # Return defaults
                return {'speed': 0.8, 'asymmetry': 10.0, 'double_support': 30.0}
                
    except Exception as e:
        print(f"Error getting patient thresholds: {e}")
        return {'speed': 0.8, 'asymmetry': 10.0, 'double_support': 30.0}

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    db_status = "connected" if DATABASE_URL else "not configured"
    
    if DATABASE_URL:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "connected"
        except:
            db_status = "connection failed"
    
    return {
        "status": "healthy",
        "database": db_status,
        "active_patients": len(manager.active_connections),
        "active_pharmacists": len(manager.pharmacist_connections)
    }

# WebSocket endpoint for Swift app real-time data
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, patient_id: str):
    await manager.connect_patient(websocket, patient_id)
    
    try:
        while True:
            # Receive data from Swift app
            data = await websocket.receive_json()
            
            # Store in database
            if data.get('data_type') == 'historical':
                # Handle batch historical data
                for record in data.get('records', []):
                    record_id = store_gait_data(record)
                    if record_id:
                        alerts = check_for_alerts(record)
                        if alerts:
                            for alert in alerts:
                                await manager.notify_pharmacists(alert)
                
                await websocket.send_json({
                    "status": "batch_received",
                    "records_processed": len(data.get('records', [])),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                # Handle real-time data
                record_id = store_gait_data(data)
                alerts = check_for_alerts(data)
                
                # Send alerts to pharmacists
                if alerts:
                    for alert in alerts:
                        await manager.notify_pharmacists(alert)
                
                # Send confirmation back to Swift app
                await websocket.send_json({
                    "status": "received",
                    "record_id": record_id,
                    "timestamp": datetime.now().isoformat(),
                    "alerts_triggered": len(alerts)
                })
                
    except WebSocketDisconnect:
        manager.disconnect_patient(patient_id)
    except Exception as e:
        print(f"WebSocket error for patient {patient_id}: {e}")
        manager.disconnect_patient(patient_id)

# WebSocket endpoint for pharmacist dashboard
@app.websocket("/pharmacist_ws") 
async def pharmacist_websocket(websocket: WebSocket):
    await manager.connect_pharmacist(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to alert stream",
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            # Keep connection alive and handle any pharmacist actions
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            try:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                })
            except:
                break
                
    except WebSocketDisconnect:
        manager.disconnect_pharmacist(websocket)
    except Exception as e:
        print(f"Pharmacist WebSocket error: {e}")
        manager.disconnect_pharmacist(websocket)

# REST API endpoints
@app.post("/api/gait-data")
async def receive_gait_data(data: dict):
    """HTTP endpoint as alternative to WebSocket"""
    record_id = store_gait_data(data)
    alerts = check_for_alerts(data)
    
    if alerts:
        for alert in alerts:
            await manager.notify_pharmacists(alert)
    
    return {
        "status": "success", 
        "record_id": record_id,
        "alerts": len(alerts),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/patient/{patient_id}/data")
async def get_patient_data(patient_id: str, days: int = 30):
    """Get patient gait data for analysis"""
    if not DATABASE_URL:
        return []
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM gait_records 
                WHERE patient_id = :patient_id 
                AND timestamp >= NOW() - INTERVAL ':days days'
                ORDER BY timestamp DESC
                LIMIT 1000
            """), {'patient_id': patient_id, 'days': days})
            
            columns = result.keys()
            data = [dict(zip(columns, row)) for row in result.fetchall()]
            
            # Convert timestamps to strings for JSON serialization
            for record in data:
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
            
            return data
            
    except Exception as e:
        print(f"Error getting patient data: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/patients")
async def list_patients():
    """Get all patients with recent data"""
    if not DATABASE_URL:
        return []
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    patient_id, 
                    COUNT(*) as total_records,
                    MAX(timestamp) as last_update,
                    MIN(timestamp) as first_record
                FROM gait_records 
                GROUP BY patient_id
                ORDER BY last_update DESC
                LIMIT 50
            """))
            
            columns = result.keys()
            data = [dict(zip(columns, row)) for row in result.fetchall()]
            
            # Convert timestamps to strings
            for record in data:
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
            
            return data
            
    except Exception as e:
        print(f"Error listing patients: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/api/medication-change")
async def log_medication_change(change: dict):
    """Log medication changes for correlation analysis"""
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Database not available")
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO medication_changes (
                    patient_id, change_date, medication_name,
                    old_dosage, new_dosage, reason, pharmacist_id
                ) VALUES (
                    :patient_id, :change_date, :medication_name,
                    :old_dosage, :new_dosage, :reason, :pharmacist_id
                ) RETURNING id
            """), {
                'patient_id': change.get('patient_id'),
                'change_date': change.get('change_date'),
                'medication_name': change.get('medication_name'),
                'old_dosage': change.get('old_dosage'),
                'new_dosage': change.get('new_dosage'),
                'reason': change.get('reason'),
                'pharmacist_id': change.get('pharmacist_id')
            })
            
            conn.commit()
            record_id = result.fetchone()[0]
            print(f"Logged medication change for patient {change.get('patient_id')}")
            return {"status": "success", "id": str(record_id)}
            
    except Exception as e:
        print(f"Database error logging medication change: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/patient/{patient_id}/medication-history")
async def get_medication_history(patient_id: str):
    """Get medication change history for a patient"""
    if not DATABASE_URL:
        return []
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM medication_changes 
                WHERE patient_id = :patient_id
                ORDER BY change_date DESC
                LIMIT 100
            """), {'patient_id': patient_id})
            
            columns = result.keys()
            data = [dict(zip(columns, row)) for row in result.fetchall()]
            
            # Convert timestamps to strings for JSON serialization
            for record in data:
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
            
            return data
            
    except Exception as e:
        print(f"Error getting medication history: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/api/patient/{patient_id}/thresholds")
async def update_patient_thresholds(patient_id: str, thresholds: dict):
    """Update patient-specific alert thresholds"""
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Database not available")
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Use UPSERT (INSERT ... ON CONFLICT) for PostgreSQL
            conn.execute(text("""
                INSERT INTO patient_thresholds (
                    patient_id, walking_speed_threshold, asymmetry_threshold, double_support_threshold
                ) VALUES (
                    :patient_id, :speed_threshold, :asymmetry_threshold, :support_threshold
                )
                ON CONFLICT (patient_id) 
                DO UPDATE SET
                    walking_speed_threshold = EXCLUDED.walking_speed_threshold,
                    asymmetry_threshold = EXCLUDED.asymmetry_threshold,
                    double_support_threshold = EXCLUDED.double_support_threshold,
                    updated_at = CURRENT_TIMESTAMP
            """), {
                'patient_id': patient_id,
                'speed_threshold': thresholds.get('walking_speed_threshold', 0.8),
                'asymmetry_threshold': thresholds.get('asymmetry_threshold', 10.0),
                'support_threshold': thresholds.get('double_support_threshold', 30.0)
            })
            
            conn.commit()
            print(f"Updated thresholds for patient {patient_id}")
            
            return {
                "status": "success",
                "patient_id": patient_id,
                "thresholds": thresholds,
                "updated_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"Error updating patient thresholds: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/patient/{patient_id}/thresholds")
async def get_patient_thresholds_api(patient_id: str):
    """Get patient-specific thresholds via API"""
    if not DATABASE_URL:
        return {"speed": 0.8, "asymmetry": 10.0, "double_support": 30.0}
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT walking_speed_threshold, asymmetry_threshold, double_support_threshold, updated_at
                FROM patient_thresholds 
                WHERE patient_id = :patient_id
            """), {'patient_id': patient_id})
            
            row = result.fetchone()
            if row:
                return {
                    "patient_id": patient_id,
                    "walking_speed_threshold": float(row[0]),
                    "asymmetry_threshold": float(row[1]),
                    "double_support_threshold": float(row[2]),
                    "updated_at": row[3].isoformat() if row[3] else None
                }
            else:
                # Return defaults if no custom thresholds set
                return {
                    "patient_id": patient_id,
                    "walking_speed_threshold": 0.8,
                    "asymmetry_threshold": 10.0,
                    "double_support_threshold": 30.0,
                    "updated_at": None
                }
                
    except Exception as e:
        print(f"Error getting patient thresholds: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/alerts/recent")
async def get_recent_alerts(hours: int = 24):
    """Get recent alerts across all patients"""
    if not DATABASE_URL:
        return []
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT patient_id, timestamp, walking_speed, walking_asymmetry, 
                       double_support_time, asymmetry_alert, double_support_alert,
                       speed_category
                FROM gait_records 
                WHERE timestamp >= NOW() - INTERVAL ':hours hours'
                AND (asymmetry_alert = true OR double_support_alert = true OR walking_speed < 0.8)
                ORDER BY timestamp DESC
                LIMIT 100
            """), {'hours': hours})
            
            columns = result.keys()
            data = [dict(zip(columns, row)) for row in result.fetchall()]
            
            # Convert timestamps and format alerts
            alerts = []
            for record in data:
                record_time = record['timestamp'].isoformat() if record['timestamp'] else None
                
                # Check for speed alerts
                if record.get('walking_speed') and record['walking_speed'] < 0.8:
                    alerts.append({
                        'type': 'walking_speed_low',
                        'patient_id': record['patient_id'],
                        'timestamp': record_time,
                        'value': record['walking_speed'],
                        'severity': 'high',
                        'message': f'Low walking speed: {record["walking_speed"]:.2f} m/s'
                    })
                
                # Check for asymmetry alerts
                if record.get('asymmetry_alert'):
                    alerts.append({
                        'type': 'asymmetry_high',
                        'patient_id': record['patient_id'],
                        'timestamp': record_time,
                        'value': record.get('walking_asymmetry'),
                        'severity': 'medium',
                        'message': f'High asymmetry: {record.get("walking_asymmetry", "N/A")}%'
                    })
                
                # Check for double support alerts
                if record.get('double_support_alert'):
                    alerts.append({
                        'type': 'double_support_high',
                        'patient_id': record['patient_id'],
                        'timestamp': record_time,
                        'value': record.get('double_support_time'),
                        'severity': 'medium',
                        'message': f'High double support: {record.get("double_support_time", "N/A")}%'
                    })
            
            return alerts
            
    except Exception as e:
        print(f"Error getting recent alerts: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/api/stats")
async def get_system_stats():
    """Get overall system statistics"""
    if not DATABASE_URL:
        return {"error": "Database not available"}
        
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Get patient count
            patient_count = conn.execute(text("""
                SELECT COUNT(DISTINCT patient_id) FROM gait_records
            """)).scalar()
            
            # Get total records
            total_records = conn.execute(text("""
                SELECT COUNT(*) FROM gait_records
            """)).scalar()
            
            # Get recent activity (last 24 hours)
            recent_activity = conn.execute(text("""
                SELECT COUNT(*) FROM gait_records 
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """)).scalar()
            
            # Get alert count (last 24 hours)
            recent_alerts = conn.execute(text("""
                SELECT COUNT(*) FROM gait_records 
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                AND (asymmetry_alert = true OR double_support_alert = true OR walking_speed < 0.8)
            """)).scalar()
            
            return {
                "total_patients": patient_count,
                "total_records": total_records,
                "recent_activity_24h": recent_activity,
                "recent_alerts_24h": recent_alerts,
                "active_connections": len(manager.active_connections),
                "pharmacist_connections": len(manager.pharmacist_connections),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "Gait Monitoring API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "websocket_patient": "/ws?patient_id={patient_id}",
            "websocket_pharmacist": "/pharmacist_ws",
            "gait_data": "/api/gait-data",
            "patients": "/api/patients",
            "patient_data": "/api/patient/{patient_id}/data",
            "medication_change": "/api/medication-change",
            "medication_history": "/api/patient/{patient_id}/medication-history",
            "patient_thresholds": "/api/patient/{patient_id}/thresholds",
            "recent_alerts": "/api/alerts/recent",
            "system_stats": "/api/stats"
        }
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Endpoint not found", "status_code": 404}

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"error": "Internal server error", "status_code": 500}

# Run the application
if __name__ == "__main__":
    import uvicorn
    
    print(f"Starting Gait Monitoring API on port {PORT}")
    print(f"Database URL: {'configured' if DATABASE_URL else 'not configured'}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,  # Set to False for production
        access_log=True
    )
