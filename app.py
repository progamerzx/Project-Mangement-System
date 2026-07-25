from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from database import (
    init_db, get_projects, get_project, create_project, delete_project,
    get_tasks_for_project, create_task, update_task_status, get_dashboard_stats
)

app = Flask(__name__)

# Load config from Key Vault / Environment
Config.load_config()
print("SERVER :", Config.DB_SERVER)
print("DATABASE :", Config.DB_NAME)
app.config.from_object(Config)

# Initialize database schema
init_db()

@app.route('/')
def index():
    """Home dashboard and project listing."""
    stats = get_dashboard_stats()
    projects = get_projects()
    return render_template('index.html', stats=stats, projects=projects)

@app.route('/project/add', methods=['POST'])
def add_project():
    """Handles project creation."""
    name = request.form.get('name')
    description = request.form.get('description')
    if not name:
        flash("Project name is required!", "danger")
        return redirect(url_for('index'))
    
    success = create_project(name, description)
    if success:
        flash("Project created successfully!", "success")
    else:
        flash("Failed to create project. Please verify database connection and configuration.", "danger")
    return redirect(url_for('index'))

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    """View details of a single project, including list of tasks grouped by status."""
    project = get_project(project_id)
    if not project:
        flash("Project not found!", "danger")
        return redirect(url_for('index'))
    
    tasks = get_tasks_for_project(project_id)
    
    # Categorize tasks for grid visualization
    todo_tasks = [t for t in tasks if t['status'] == 'To Do']
    inprogress_tasks = [t for t in tasks if t['status'] == 'In Progress']
    done_tasks = [t for t in tasks if t['status'] == 'Done']
    
    return render_template(
        'project_detail.html',
        project=project,
        todo_tasks=todo_tasks,
        inprogress_tasks=inprogress_tasks,
        done_tasks=done_tasks
    )

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def remove_project(project_id):
    """Deletes a project. CASCADE in DB will handle deleting tasks."""
    success = delete_project(project_id)
    if success:
        flash("Project and all its associated tasks have been deleted.", "success")
    else:
        flash("Failed to delete project.", "danger")
    return redirect(url_for('index'))

@app.route('/project/<int:project_id>/task/add', methods=['POST'])
def add_task(project_id):
    """Adds a task to a project."""
    title = request.form.get('title')
    description = request.form.get('description')
    status = request.form.get('status', 'To Do')
    due_date = request.form.get('due_date')
    
    if not title:
        flash("Task title is required!", "danger")
        return redirect(url_for('project_detail', project_id=project_id))
    
    success = create_task(project_id, title, description, status, due_date)
    if success:
        flash("Task added successfully!", "success")
    else:
        flash("Failed to add task.", "danger")
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/task/<int:task_id>/update-status', methods=['POST'])
def change_task_status(task_id):
    """Updates status of a task."""
    project_id = request.form.get('project_id')
    status = request.form.get('status')
    
    if not status or not project_id:
        flash("Invalid arguments provided.", "danger")
        return redirect(url_for('index'))
        
    success = update_task_status(task_id, status)
    if success:
        flash("Task status updated successfully.", "success")
    else:
        flash("Failed to update task status.", "danger")
    return redirect(url_for('project_detail', project_id=project_id))

if __name__ == '__main__':
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
