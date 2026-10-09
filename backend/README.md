# Installing the IFusion Backend

This guide provides step-by-step instructions to set up the IFusion Backend project. We will cover cloning the repository, setting up a virtual environment, configuring PostgreSQL, installing Poetry, installing project dependencies, and starting the application with Uvicorn.

## Prerequisites

- Python 3.10+ installed on your system.
- Git installed to clone the repository.
- PostgreSQL installed and running (if your project requires it).

## Steps

### 1: Clone the project Repository

Clone the Repository
Clone your FastAPI backend project repository from GitHub or any other version control system.

```bash
git clone https://github.com/khifusion/backend.git

cd backend
```

Run the following command to create an `.env` file from the existing `.env-example` template

```bash
cp .env-example .env
```

### 2: Create and Activate a Virtual Environment

Create a virtual environment for your project to isolate dependencies.

```bash
python3 -m venv venv
```

Activate the virtual environment:

- macOS/Linux:

```bash
source venv/bin/activate
```

- Windows:

```cmd
venv\Scripts\activate
```

### 3: Configure PostgreSQL

Since this project uses PostgreSQL, we will configure the database connection.

Change the PostgreSQL configuration parameters in the env file with your existing PostgreSQL Server Configuration.

```env
POSTGRES_SERVER=localhost
POSTGRES_USER=<postgres_user>
POSTGRES_PASSWORD=<postgres_user_password>
POSTGRES_DB=<database_name>
```

### 4: Install Poetry

Install Poetry to manage dependencies and virtual environments inside your project.

```bash
pip3 install --upgrade pip
```

After upgrading your pip, install poetry using the following command

```bash
pip3 install poetry
```

### 5: Install Project Dependencies

Use Poetry to install the project dependencies specified in pyproject.toml.

```bash
poetry install
```

Note that if developing in containerized environments, e.g. docker containers (Dockerfiles) or Codespaces, this may fail due to the way poetry installs dependencies in docker containers. In that case, use the `container-install.sh` script

```bash
./container-install.sh
```

### 6: Install the pre-commit Hook Locally

```bash
poetry run pre-commit install
```

### 7: Start the FastAPI Application with Uvicorn

Run the FastAPI application using Uvicorn.

```bash
uvicorn app.main:app --reload
```
