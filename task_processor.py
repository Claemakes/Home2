"""
Background Task Processing Module for GlassRain

This module provides a background task processing system using Flask-Executor
for running long-running operations without blocking the web request.
"""

import logging
import time
import uuid
import json
import traceback
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError, CancelledError
from flask import Flask, current_app, request, g, jsonify
from flask_executor import Executor

# Configure logging
logger = logging.getLogger(__name__)

# Global task registry
_task_registry = {}

class TaskStatus:
    """Task status constants"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    TIMEOUT = 'timeout'

class Task:
    """Task object to track background jobs"""
    def __init__(self, task_id=None, name=None, description=None):
        self.task_id = task_id or str(uuid.uuid4())
        self.name = name or "background_task"
        self.description = description or "Background task"
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.progress = 0.0
        self.progress_message = None
        self.user_id = None  # Can be set for task filtering by user
    
    def to_dict(self):
        """Convert task to dictionary"""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': round(self.progress, 2),
            'progress_message': self.progress_message,
            'result': self.result if self.status == TaskStatus.COMPLETED else None,
            'error': self.error if self.status == TaskStatus.FAILED else None,
            'user_id': self.user_id
        }
    
    def update_progress(self, progress, message=None):
        """Update task progress"""
        self.progress = min(max(0.0, float(progress)), 100.0)
        self.progress_message = message
        return self

def init_executor(app, max_workers=2):
    """
    Initialize the executor for the application.
    
    Args:
        app: Flask application instance
        max_workers: Maximum number of worker threads
    """
    executor = Executor(app)
    executor.futures = {}  # Store futures by task_id
    app.executor = executor
    app.config['EXECUTOR_MAX_WORKERS'] = max_workers
    app.config['EXECUTOR_TYPE'] = 'thread'
    
    logger.info(f"Task processor initialized with {max_workers} workers")
    return executor

def get_executor():
    """
    Get the executor from the current application.
    
    Returns:
        Executor instance
    """
    if hasattr(current_app, 'executor'):
        return current_app.executor
    
    # If no executor, create a standalone one (for testing/non-Flask contexts)
    executor = ThreadPoolExecutor(max_workers=2)
    
    # Add a futures dict for tracking
    executor.futures = {}
    
    return executor

def submit_task(func, *args, name=None, description=None, timeout=None, user_id=None, **kwargs):
    """
    Submit a task to be executed in the background.
    
    Args:
        func: Function to execute
        *args: Positional arguments for func
        name: Task name
        description: Task description
        timeout: Timeout in seconds
        user_id: User ID for task filtering
        **kwargs: Keyword arguments for func
        
    Returns:
        Task object
    """
    # Create task object
    task = Task(name=name, description=description)
    task.user_id = user_id
    
    # Register task
    _task_registry[task.task_id] = task
    
    # Get executor
    executor = get_executor()
    
    # Define the task wrapper
    def task_wrapper():
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        # Set thread-local task object
        g.current_task = task
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            return result
        except Exception as e:
            # Handle errors
            error_details = {
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            task.error = error_details
            task.status = TaskStatus.FAILED
            logger.error(f"Task {task.task_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            raise e
        finally:
            task.completed_at = datetime.now()
    
    # Submit the task
    future = executor.submit(task_wrapper)
    executor.futures[task.task_id] = future
    
    # Set up timeout if specified
    if timeout:
        def check_timeout():
            """Check if task has timed out"""
            try:
                future.result(timeout=timeout)
            except TimeoutError:
                task.status = TaskStatus.TIMEOUT
                task.error = {'message': f'Task timed out after {timeout} seconds'}
                task.completed_at = datetime.now()
                logger.warning(f"Task {task.task_id} timed out after {timeout} seconds")
                future.cancel()
        
        # Submit the timeout checker
        executor.submit(check_timeout)
    
    logger.info(f"Submitted task {task.task_id}: {task.name}")
    return task

def get_task(task_id):
    """
    Get a task by ID.
    
    Args:
        task_id: Task ID
        
    Returns:
        Task object or None if not found
    """
    return _task_registry.get(task_id)

def get_all_tasks(user_id=None, limit=20, status=None):
    """
    Get all tasks, optionally filtered.
    
    Args:
        user_id: Filter by user ID
        limit: Maximum number of tasks to return
        status: Filter by status
        
    Returns:
        List of Task objects
    """
    tasks = list(_task_registry.values())
    
    # Apply filters
    if user_id:
        tasks = [t for t in tasks if t.user_id == user_id]
    
    if status:
        tasks = [t for t in tasks if t.status == status]
    
    # Sort by created_at (newest first)
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    
    # Apply limit
    return tasks[:limit]

def cancel_task(task_id):
    """
    Cancel a task.
    
    Args:
        task_id: Task ID
        
    Returns:
        bool: True if task was cancelled, False otherwise
    """
    task = get_task(task_id)
    
    if not task:
        return False
    
    executor = get_executor()
    
    if task_id in executor.futures:
        future = executor.futures[task_id]
        
        # Only cancel if not already done
        if not future.done():
            # Attempt to cancel
            cancelled = future.cancel()
            
            if cancelled:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                logger.info(f"Task {task_id} cancelled")
                return True
    
    return False

def task_progress(task_id, progress, message=None):
    """
    Update task progress.
    
    Args:
        task_id: Task ID
        progress: Progress value (0-100)
        message: Progress message
        
    Returns:
        Task object or None if not found
    """
    task = get_task(task_id)
    
    if task:
        task.update_progress(progress, message)
    
    return task

def cleanup_old_tasks(max_age_hours=24):
    """
    Cleanup old completed tasks.
    
    Args:
        max_age_hours: Maximum age in hours
        
    Returns:
        int: Number of tasks removed
    """
    now = datetime.now()
    task_ids = list(_task_registry.keys())
    removed = 0
    
    for task_id in task_ids:
        task = _task_registry[task_id]
        
        # Only remove completed, failed, cancelled, or timeout tasks
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                         TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
            # Calculate age in hours
            if task.completed_at:
                age_hours = (now - task.completed_at).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    del _task_registry[task_id]
                    removed += 1
    
    return removed

def background_task(name=None, description=None, timeout=None):
    """
    Decorator for functions that should run as background tasks.
    
    Args:
        name: Task name
        description: Task description
        timeout: Timeout in seconds
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user_id from request if available
            user_id = None
            
            if request and hasattr(request, 'user_id'):
                user_id = request.user_id
            
            # Submit task
            task_name = name or f.__name__
            task_desc = description or f"Background task: {f.__name__}"
            
            task = submit_task(
                f, *args, 
                name=task_name, 
                description=task_desc,
                timeout=timeout,
                user_id=user_id,
                **kwargs
            )
            
            return jsonify({
                'task_id': task.task_id,
                'status': task.status,
                'name': task.name,
                'description': task.description
            })
        
        # Add reference to the original function
        decorated_function.original_func = f
        
        # Add a synchronous execution method
        decorated_function.execute_sync = f
        
        # Add an async submission method that returns the Task
        @wraps(f)
        def submit_async(*args, **kwargs):
            return submit_task(
                f, *args,
                name=name or f.__name__,
                description=description or f"Background task: {f.__name__}",
                timeout=timeout,
                **kwargs
            )
        
        decorated_function.submit = submit_async
        
        return decorated_function
    
    return decorator

def init_task_routes(app):
    """
    Initialize task management routes.
    
    Args:
        app: Flask application instance
    """
    @app.route('/api/tasks', methods=['GET'])
    def api_get_tasks():
        """API endpoint to get all tasks"""
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        limit = request.args.get('limit', 20, type=int)
        
        tasks = get_all_tasks(user_id=user_id, status=status, limit=limit)
        
        return jsonify({
            'tasks': [task.to_dict() for task in tasks]
        })
    
    @app.route('/api/tasks/<task_id>', methods=['GET'])
    def api_get_task(task_id):
        """API endpoint to get a specific task"""
        task = get_task(task_id)
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify(task.to_dict())
    
    @app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
    def api_cancel_task(task_id):
        """API endpoint to cancel a task"""
        result = cancel_task(task_id)
        
        if not result:
            return jsonify({'error': 'Could not cancel task'}), 400
        
        return jsonify({'message': 'Task cancelled successfully'})
    
    logger.info("Task management routes initialized")