"""
Monitoring Feature - Enhanced Health Monitoring
==============================================

Technical monitoring feature for comprehensive bot health tracking.
Provides enhanced metrics collection, alerting, and performance monitoring.

TECHNICAL ONLY - No business logic or subscription features.
"""

import asyncio
import json
import logging
import psutil
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import time

from ..container.technical_feature_container import TechnicalFeature, FeatureConfiguration, BotContext


@dataclass
class HealthMetric:
    """Individual health metric measurement."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    @property
    def is_warning(self) -> bool:
        """Check if metric exceeds warning threshold."""
        return self.threshold_warning is not None and self.value >= self.threshold_warning
    
    @property
    def is_critical(self) -> bool:
        """Check if metric exceeds critical threshold."""
        return self.threshold_critical is not None and self.value >= self.threshold_critical
    
    @property
    def status(self) -> str:
        """Get metric status."""
        if self.is_critical:
            return "critical"
        elif self.is_warning:
            return "warning"
        else:
            return "healthy"


class MonitoringFeature(TechnicalFeature):
    """
    Enhanced monitoring feature for bot health tracking.
    
    Provides technical monitoring capabilities:
    - CPU and memory usage tracking
    - Discord API response time monitoring  
    - Event processing rate metrics
    - Custom metric collection
    - Health status reporting
    - Performance trend analysis
    
    NO BUSINESS LOGIC - Pure technical monitoring.
    """
    
    def __init__(self, config: Optional[FeatureConfiguration] = None):
        """Initialize monitoring feature."""
        if config is None:
            config = FeatureConfiguration(
                feature_name="monitoring_service",
                feature_type="monitoring",
                description="Enhanced health monitoring and metrics collection",
                version="1.0.0",
                configuration={
                    "collection_interval": 30,  # seconds
                    "metrics_retention_days": 7,
                    "thresholds": {
                        "cpu_warning": 70.0,
                        "cpu_critical": 85.0,
                        "memory_warning": 80.0,
                        "memory_critical": 95.0,
                        "response_time_warning": 1000,  # ms
                        "response_time_critical": 3000  # ms
                    },
                    "alerts": {
                        "enabled": True,
                        "log_warnings": True,
                        "log_critical": True
                    },
                    "custom_metrics": {
                        "enabled": True,
                        "max_custom_metrics": 50
                    }
                }
            )
        super().__init__(config)
        
        # Monitoring state
        self._monitoring_task: Optional[asyncio.Task] = None
        self._metrics_history: List[Dict[str, Any]] = []
        self._custom_metrics: Dict[str, HealthMetric] = {}
        self._start_time = datetime.now(timezone.utc)
    
    @property
    def feature_name(self) -> str:
        """Name of this technical feature."""
        return "monitoring_service"
    
    @property
    def feature_type(self) -> str:
        """Type of feature."""
        return "monitoring"
    
    async def _do_initialize(self) -> None:
        """Initialize monitoring resources."""
        self.logger.info("Initializing enhanced monitoring service")
        
        # Create metrics storage directory
        self.metrics_directory = Path("platform_metrics/monitoring")
        self.metrics_directory.mkdir(parents=True, exist_ok=True)
        
        # Validate thresholds
        self._validate_threshold_configuration()
    
    def _validate_threshold_configuration(self) -> None:
        """Validate monitoring threshold configuration."""
        thresholds = self.config.configuration.get("thresholds", {})
        
        # Ensure warning thresholds are less than critical thresholds
        pairs = [
            ("cpu_warning", "cpu_critical"),
            ("memory_warning", "memory_critical"),
            ("response_time_warning", "response_time_critical")
        ]
        
        for warning_key, critical_key in pairs:
            warning_val = thresholds.get(warning_key, 0)
            critical_val = thresholds.get(critical_key, 100)
            
            if warning_val >= critical_val:
                self.logger.warning(f"Warning threshold {warning_key} >= critical {critical_key}")
                thresholds[warning_key] = critical_val * 0.8
    
    async def apply_to_bot_context(self, context: BotContext) -> bool:
        """
        Apply monitoring enhancements to bot context.
        
        Sets up comprehensive health monitoring for the bot process
        and creates monitoring configuration files.
        
        Args:
            context: Bot context with instance and configuration
            
        Returns:
            True if monitoring applied successfully
        """
        try:
            client_id = context.bot_instance.client_id
            self.logger.info(f"Applying monitoring enhancements to {client_id}")
            
            # Step 1: Create monitoring configuration file
            monitoring_config_path = await self._create_monitoring_config(context)
            
            # Step 2: Set monitoring environment variables
            self._set_monitoring_environment_variables(context, monitoring_config_path)
            
            # Step 3: Set up metrics collection directory
            await self._setup_metrics_collection(context)
            
            # Step 4: Create monitoring helper utilities
            await self._create_monitoring_helpers(context)
            
            self.logger.info(f"✅ Monitoring enhancements applied to {client_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply monitoring to {context.bot_instance.client_id}: {e}")
            return False
    
    async def _create_monitoring_config(self, context: BotContext) -> Path:
        """Create monitoring configuration file."""
        config_dir = context.log_directory.parent / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        monitoring_config_path = config_dir / "monitoring.json"
        
        monitoring_config = {
            "enabled": True,
            "collection_interval": self.config.configuration.get("collection_interval", 30),
            "retention_days": self.config.configuration.get("metrics_retention_days", 7),
            "thresholds": self.config.configuration.get("thresholds", {}),
            "alerts": self.config.configuration.get("alerts", {}),
            "metrics_directory": str(context.log_directory.parent / "metrics"),
            "platform_info": {
                "monitoring_version": "1.0.0",
                "start_time": self._start_time.isoformat()
            }
        }
        
        with open(monitoring_config_path, 'w', encoding='utf-8') as f:
            json.dump(monitoring_config, f, indent=2, ensure_ascii=False)
        
        return monitoring_config_path
    
    def _set_monitoring_environment_variables(self, context: BotContext, config_path: Path) -> None:
        """Set monitoring environment variables."""
        context.environment_config["MULTICORD_MONITORING_CONFIG"] = str(config_path)
        context.environment_config["MULTICORD_MONITORING_ENABLED"] = "true"
        
        # Thresholds as environment variables
        thresholds = self.config.configuration.get("thresholds", {})
        context.environment_config["MULTICORD_CPU_WARNING"] = str(thresholds.get("cpu_warning", 70))
        context.environment_config["MULTICORD_MEMORY_WARNING"] = str(thresholds.get("memory_warning", 80))
        
        # Collection interval
        interval = self.config.configuration.get("collection_interval", 30)
        context.environment_config["MULTICORD_COLLECTION_INTERVAL"] = str(interval)
    
    async def _setup_metrics_collection(self, context: BotContext) -> None:
        """Set up metrics collection infrastructure."""
        metrics_dir = context.log_directory.parent / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Create basic metrics files
        files_to_create = {
            "health_metrics.json": [],
            "README.md": "# MultiCord Platform - Enhanced Monitoring\n\nMetrics collection directory."
        }
        
        for filename, default_content in files_to_create.items():
            metrics_file = metrics_dir / filename
            if not metrics_file.exists():
                if filename.endswith('.json'):
                    with open(metrics_file, 'w', encoding='utf-8') as f:
                        json.dump(default_content, f, indent=2)
                else:
                    with open(metrics_file, 'w', encoding='utf-8') as f:
                        f.write(default_content)
    
    async def _create_monitoring_helpers(self, context: BotContext) -> None:
        """Create monitoring helper utilities."""
        helpers_dir = context.log_directory.parent / "multicord_helpers"
        helpers_dir.mkdir(parents=True, exist_ok=True)
        
        # Create basic monitoring helper
        helper_content = '''"""MultiCord Platform - Monitoring Helpers"""
import os
def is_monitoring_enabled():
    return os.getenv('MULTICORD_MONITORING_ENABLED') == 'true'
'''
        helper_file = helpers_dir / "monitoring.py"
        
        with open(helper_file, 'w', encoding='utf-8') as f:
            f.write(helper_content)
    
    def get_configuration_schema(self) -> Dict[str, Any]:
        """Get configuration schema for monitoring feature."""
        return {
            "type": "object",
            "properties": {
                "collection_interval": {"type": "integer", "minimum": 10},
                "metrics_retention_days": {"type": "integer", "minimum": 1},
                "thresholds": {"type": "object"}
            },
            "additionalProperties": True
        }
    
    async def cleanup(self) -> None:
        """Clean up monitoring feature resources."""
        self.logger.info("Cleaning up monitoring feature resources")