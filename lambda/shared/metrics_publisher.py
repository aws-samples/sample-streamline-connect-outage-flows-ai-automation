"""CloudWatch metrics publishing utilities."""

from typing import Optional
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit


class MetricsPublisher:
    """Utility for publishing CloudWatch metrics with consistent patterns."""
    
    @staticmethod
    def publish_authentication_attempt(
        metrics: Metrics,
        phone_number: str,
        result: str
    ) -> None:
        """
        Publish AuthenticationAttempts metric.
        
        Args:
            metrics: Metrics instance
            phone_number: Caller phone number (will be masked)
            result: Authentication result (SUCCESS, FAILURE, MAX_RETRIES_EXCEEDED)
        """
        metrics.add_metric(
            name="AuthenticationAttempts",
            unit=MetricUnit.Count,
            value=1
        )
        
        # Mask phone number (show only last 4 digits)
        masked_phone = f"***{phone_number[-4:]}" if len(phone_number) >= 4 else "****"
        
        metrics.add_dimension(name="PhoneNumber", value=masked_phone)
        metrics.add_dimension(name="Result", value=result)
    
    @staticmethod
    def publish_prompt_update(
        metrics: Metrics,
        agent_id: str,
        result: str
    ) -> None:
        """
        Publish PromptUpdates metric.
        
        Args:
            metrics: Metrics instance
            agent_id: AI Agent ID
            result: Update result (SUCCESS, FAILURE)
        """
        metrics.add_metric(
            name="PromptUpdates",
            unit=MetricUnit.Count,
            value=1
        )
        
        metrics.add_dimension(name="AgentId", value=agent_id)
        metrics.add_dimension(name="Result", value=result)
    
    @staticmethod
    def publish_test_execution(
        metrics: Metrics,
        agent_id: str,
        result: str,
        total_tests: int,
        passed: int,
        failed: int,
        critical_failures: int
    ) -> None:
        """
        Publish TestExecutions metric.
        
        Args:
            metrics: Metrics instance
            agent_id: AI Agent ID
            result: Test result (SUCCESS, FAILURE, CRITICAL_FAILURE)
            total_tests: Total number of tests executed
            passed: Number of tests passed
            failed: Number of tests failed
            critical_failures: Number of critical failures
        """
        metrics.add_metric(
            name="TestExecutions",
            unit=MetricUnit.Count,
            value=1
        )
        
        metrics.add_dimension(name="AgentId", value=agent_id)
        metrics.add_dimension(name="Result", value=result)
        
        # Publish test statistics as separate metrics
        metrics.add_metric(
            name="TestsPassed",
            unit=MetricUnit.Count,
            value=passed
        )
        
        metrics.add_metric(
            name="TestsFailed",
            unit=MetricUnit.Count,
            value=failed
        )
        
        metrics.add_metric(
            name="CriticalFailures",
            unit=MetricUnit.Count,
            value=critical_failures
        )
    
    @staticmethod
    def publish_workflow_duration(
        metrics: Metrics,
        operation: str,
        duration_ms: float
    ) -> None:
        """
        Publish WorkflowDuration metric.
        
        Args:
            metrics: Metrics instance
            operation: Operation name (UPDATE_AGENT, RESTORE_AGENT, DISABLE_INTENT, etc.)
            duration_ms: Duration in milliseconds
        """
        metrics.add_metric(
            name="WorkflowDuration",
            unit=MetricUnit.Milliseconds,
            value=duration_ms
        )
        
        metrics.add_dimension(name="Operation", value=operation)
    
    @staticmethod
    def publish_backup_operation(
        metrics: Metrics,
        agent_id: str,
        result: str
    ) -> None:
        """
        Publish BackupOperations metric.
        
        Args:
            metrics: Metrics instance
            agent_id: AI Agent ID
            result: Backup result (SUCCESS, FAILURE)
        """
        metrics.add_metric(
            name="BackupOperations",
            unit=MetricUnit.Count,
            value=1
        )
        
        metrics.add_dimension(name="AgentId", value=agent_id)
        metrics.add_dimension(name="Result", value=result)
    
    @staticmethod
    def publish_restore_operation(
        metrics: Metrics,
        agent_id: str,
        result: str
    ) -> None:
        """
        Publish RestoreOperations metric.
        
        Args:
            metrics: Metrics instance
            agent_id: AI Agent ID
            result: Restore result (SUCCESS, FAILURE)
        """
        metrics.add_metric(
            name="RestoreOperations",
            unit=MetricUnit.Count,
            value=1
        )
        
        metrics.add_dimension(name="AgentId", value=agent_id)
        metrics.add_dimension(name="Result", value=result)
    
    @staticmethod
    def publish_intent_operation(
        metrics: Metrics,
        agent_id: str,
        operation: str,
        result: str
    ) -> None:
        """
        Publish IntentOperations metric.
        
        Args:
            metrics: Metrics instance
            agent_id: AI Agent ID
            operation: Operation type (DISABLE, ENABLE, RESTORE_ALL)
            result: Operation result (SUCCESS, FAILURE)
        """
        metrics.add_metric(
            name="IntentOperations",
            unit=MetricUnit.Count,
            value=1
        )
        
        metrics.add_dimension(name="AgentId", value=agent_id)
        metrics.add_dimension(name="Operation", value=operation)
        metrics.add_dimension(name="Result", value=result)
