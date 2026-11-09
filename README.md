# Online Attendance Management System

A desktop Attendance Management System built with **Python (Tkinter)** and **MySQL**, with role-based access for Admin, Teacher and Student.

## Features
- Role-based login: Admin, Teacher, Student
- Mark and track student attendance
- Manage students, teachers and courses
- Database-backed (MySQL) with a Tkinter interface

## Tech Stack
- Python 3
- Tkinter (GUI)
- MySQL
- mysql-connector-python, python-dotenv

## Database
Database name: `attendance_db`

## Setup
1. Install MySQL and run the SQL script to create `attendance_db`.
2. Install dependencies:
   ```
   pip install mysql-connector-python python-dotenv
   ```
3. Create a `.env` file in the project folder:
   ```
   DB_PASSWORD=your_mysql_password
   ```
4. Run the app:
   ```
   python attendance_system.py
   ```

## Author
Muhammad Abdullah