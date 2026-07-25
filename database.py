import pyodbc
import struct
from azure.identity import DefaultAzureCredential
from config import Config


def get_db_connection():
    """Establishes and returns a connection to Azure SQL Database using ODBC Driver 18 and Azure AD token authentication."""

    if not all([Config.DB_SERVER, Config.DB_NAME]):
        raise ValueError(
            "Database server or database name is not configured. "
            "Check Key Vault or environment variables."
        )

    # 1. Obtain token from Azure AD
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")

    # 2. Package token
    token_bytes = token.token.encode("utf-8")
    token_struct = struct.pack("<I", len(token_bytes)) + token_bytes

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={Config.DB_SERVER};"
        f"DATABASE={Config.DB_NAME};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

    return pyodbc.connect(conn_str, attrs_before={1256: token_struct})

def row_to_dict(cursor, row):
    """Converts a database row into a dictionary using column names."""
    if row is None:
        return None
    return dict(zip([column[0] for column in cursor.description], row))

def init_db():
    """Initializes the database schema by creating projects and tasks tables if they do not exist."""
    print("[Database] Initializing database schema...")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create projects table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='projects' AND xtype='U')
            BEGIN
                CREATE TABLE projects (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(MAX),
                    created_at DATETIME DEFAULT GETDATE()
                )
            END
        """)
        
        # Create tasks table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='tasks' AND xtype='U')
            BEGIN
                CREATE TABLE tasks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    project_id INT NOT NULL,
                    title VARCHAR(100) NOT NULL,
                    description VARCHAR(MAX),
                    status VARCHAR(20) DEFAULT 'To Do',
                    due_date DATE,
                    created_at DATETIME DEFAULT GETDATE(),
                    CONSTRAINT FK_Tasks_Projects FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            END
        """)
        
        conn.commit()
        print("[Database] Database schema initialized successfully.")
    except Exception as e:
        print(f"[Database] Error initializing database: {e}")
    finally:
        if conn:
            conn.close()

# --- Database Operations ---

def get_projects():
    """Retrieves all projects."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, created_at FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]
    except Exception as e:
        print(f"[Database] Error in get_projects: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_project(project_id):
    """Retrieves a single project by ID."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, created_at FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)
    except Exception as e:
        print(f"[Database] Error in get_project: {e}")
        return None
    finally:
        if conn:
            conn.close()

def create_project(name, description):
    """Creates a new project."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[Database] Error in create_project: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_project(project_id):
    """Deletes a project. Note: Foreign Key CASCADE will delete related tasks."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"[Database] Error in delete_project: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_tasks_for_project(project_id):
    """Retrieves all tasks for a specific project."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, project_id, title, description, status, due_date, created_at FROM tasks WHERE project_id = ? ORDER BY due_date ASC",
            (project_id,)
        )
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]
    except Exception as e:
        print(f"[Database] Error in get_tasks_for_project: {e}")
        return []
    finally:
        if conn:
            conn.close()

def create_task(project_id, title, description, status, due_date):
    """Creates a new task."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (project_id, title, description, status, due_date) VALUES (?, ?, ?, ?, ?)",
            (project_id, title, description, status, due_date if due_date else None)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[Database] Error in create_task: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_task_status(task_id, status):
    """Updates the status of a task."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (status, task_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[Database] Error in update_task_status: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_dashboard_stats():
    """Retrieves counts of projects and tasks by status for dashboard view."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count projects
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        
        # Count tasks by status
        cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        task_counts_raw = cursor.fetchall()
        
        task_stats = {'To Do': 0, 'In Progress': 0, 'Done': 0}
        for row in task_counts_raw:
            status = row[0]
            count = row[1]
            if status in task_stats:
                task_stats[status] = count
                
        total_tasks = sum(task_stats.values())
        
        return {
            'project_count': project_count,
            'task_stats': task_stats,
            'total_tasks': total_tasks
        }
    except Exception as e:
        print(f"[Database] Error in get_dashboard_stats: {e}")
        return {
            'project_count': 0,
            'task_stats': {'To Do': 0, 'In Progress': 0, 'Done': 0},
            'total_tasks': 0
        }
    finally:
        if conn:
            conn.close()
