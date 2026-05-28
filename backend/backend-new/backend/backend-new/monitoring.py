import time
import psutil
import structlog
from datetime import datetime
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('websocket_connections_active', 'Active WebSocket connections')
SCRAPING_SUCCESS = Counter('scraping_operations_total', 'Total scraping operations', ['source', 'status'])
DATA_FRESHNESS = Gauge('data_freshness_seconds', 'Seconds since last data update', ['data_type'])

# System Metrics
CPU_USAGE = Gauge('system_cpu_usage_percent', 'CPU usage percentage')
MEMORY_USAGE = Gauge('system_memory_usage_bytes', 'Memory usage in bytes')
DISK_USAGE = Gauge('system_disk_usage_percent', 'Disk usage percentage')

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.active_requests = 0
        
    async def request_middleware(self, request: Request, call_next):
        """Middleware to track request performance."""
        start_time = time.time()
        self.active_requests += 1
        
        # Extract endpoint info
        method = request.method
        path = request.url.path
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Record metrics
            duration = time.time() - start_time
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)
            REQUEST_COUNT.labels(method=method, endpoint=path, status=status_code).inc()
            
            # Log request
            logger.info(
                "request_completed",
                method=method,
                path=path,
                status_code=status_code,
                duration=duration,
                user_agent=request.headers.get("user-agent", ""),
            )
            
            return response
            
        except Exception as e:
            # Record error
            REQUEST_COUNT.labels(method=method, endpoint=path, status=500).inc()
            logger.error(
                "request_failed",
                method=method,
                path=path,
                error=str(e),
                duration=time.time() - start_time
            )
            raise
        finally:
            self.active_requests -= 1
    
    def update_system_metrics(self):
        """Update system performance metrics."""
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=1)
            CPU_USAGE.set(cpu_percent)
            
            # Memory Usage
            memory = psutil.virtual_memory()
            MEMORY_USAGE.set(memory.used)
            
            # Disk Usage
            disk = psutil.disk_usage('/')
            DISK_USAGE.set(disk.percent)
            
            logger.debug(
                "system_metrics_updated",
                cpu_percent=cpu_percent,
                memory_used_gb=round(memory.used / (1024**3), 2),
                disk_percent=disk.percent
            )
            
        except Exception as e:
            logger.error("failed_to_update_system_metrics", error=str(e))
    
    def track_scraping_operation(self, source: str, success: bool):
        """Track scraping operation results."""
        status = "success" if success else "failure"
        SCRAPING_SUCCESS.labels(source=source, status=status).inc()
        
        logger.info(
            "scraping_operation",
            source=source,
            success=success,
            timestamp=datetime.now().isoformat()
        )
    
    def update_data_freshness(self, data_type: str, last_update: datetime):
        """Update data freshness metrics."""
        freshness = (datetime.now() - last_update).total_seconds()
        DATA_FRESHNESS.labels(data_type=data_type).set(freshness)
    
    def track_websocket_connection(self, connected: bool):
        """Track WebSocket connections."""
        if connected:
            ACTIVE_CONNECTIONS.inc()
        else:
            ACTIVE_CONNECTIONS.dec()

# Global monitor instance
monitor = PerformanceMonitor()

def get_metrics_response():
    """Generate Prometheus metrics response."""
    return PlainTextResponse(generate_latest())

def get_health_status() -> Dict[str, Any]:
    """Get application health status."""
    uptime = time.time() - monitor.start_time
    
    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 2),
        "active_requests": monitor.active_requests,
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        },
        "timestamp": datetime.now().isoformat()
    }
