# Perma's Scoop REST API 🍨
A minimal REST API for the [Scoop web archiving library](https://github.com/harvard-lil/scoop)

This iteration is built around:
- [Flask](https://flask.palletsprojects.com/en/2.3.x/)
- [Custom Flask commands](https://flask.palletsprojects.com/en/2.3.x/cli/#custom-commands)
- [PostgreSQL](https://www.postgresql.org/)
- [Celery](https://docs.celeryq.dev/en/stable/)

---

## Summary
- [Preamble](#preamble)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [CLI](#cli)
- [API](#api)
- [Asynchronous tasks with Celery](#asynchronous-tasks-with-celery)
- [Deployment](#deployment)
- [Tests and linting](#tests-and-linting)

---

## Preamble

> ⚠️ Not ready for public release

This codebase was originally designed as a prototype for a generic-purpose REST API for [Scoop](https://github.com/harvard-lil/scoop).

A decision was made to quickly solidify it so it can be used as Perma.cc's capture backend. 
This forced the consolidation of features towards less genericity, in order to quickly meet Perma.cc's specific needs. 

This API can be used in production in the context of Perma.cc, but could be forked to become a [Perma Tool](https://tools.perma.cc).

[👆 Back to the summary](#summary)

---

## Getting Started

The quickest way to get started is to use our Dockerized development environment, but you may prefer a manual installation.

Note: this application has only been tested on UNIX-like systems.

### Docker Compose

#### 1. Machine-level dependencies
- [Docker](https://docs.docker.com/get-docker/)


#### 2. Option 1: Spin up a bare-bones environment

Run `docker compose up` to spin up two containers.

All project-level dependencies will be installed.

The application's database will be created and populated with the application's tables.

The two containers will sit ready to receive commands: in another terminal window, run
```bash
docker compose exec web bash
```
to get a bash terminal in the application's `web` container, or run
```bash
docker compose exec web <command>
```
to execute commands in the container from your own shell.

See the [manual installation](#manual-installation), [CLI](#CLI), [API](#API), and [Celery](#asynchronous-tasks-with-celery) sections of this document for more details on available commands.

#### 3. Option 2: Spin up a working instance

Or, tweak a few settings in `docker-compose.yml` to arrange for a fully-functional instance to spin up in the background.

 Set `START_CRON=true`, `START_FLASK_SERVER=true`, and `START_CELERY=true`. Uncomment the `DISPLAY` and `CREATE_ACCESS_KEY_WITH_LABEL` lines so that Xvfb will be turned on, and so that an access key will be created for you.

Then run `docker compose up`.

When the application is ready, your access key will be printed to stdout; it will also be written to `docker/access_keys/access_key.txt` for safe keeping.

You should now be able to use that access key to interact with the Scoop REST API. For example, to attempt your first capture:

```
curl -X POST -H "Content-Type: application/json" -H "Access-Key: your-access-key" -d '{"url": "http://example.com"}' http://localhost:5000/capture
```

See the [manual installation](#manual-installation), [CLI](#CLI) and [API](#API) sections of this document for more details on available routes and commands.

[👆 Back to the summary](#summary)

### Manual Installation

#### 1. Machine-level dependencies
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/en)
- [Poetry](https://python-poetry.org/)
- [PostgreSQL](https://www.postgresql.org/)
- [Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/)

#### 2. Project-level dependencies
The following shortcut will:
- Install all Python dependencies using `poetry`
- Install Scoop and related dependencies using `npm`
- Pull the latest version of Amazon RDS CA certificates as `rds.pem` (needed if reaching one of our remote DBs).

```bash
bash install.sh
```

#### 3. Setting up PostgreSQL

The Scoop REST API only needs an empty database to operate, which it can then programmatically populate.

```SQL
CREATE DATABASE scoop_api;
```

For local development and tests, PostgreSQL can be installed and automatically setup via `brew install postgresql` on Mac OS.


#### 4. Setting up Redis

For local development and tests, Redis can be installed and automatically setup via `brew install redis` on Mac OS.

You can run it in the foreground with the command `redis-server`.


#### 5. Setting up environment variables

Copy `example.env` as `.env` and populate the missing values.


#### 6. Setting up the database tables
The following command creates and initializes the database tables for the application to use. 

```bash
poetry run flask create-tables
```

#### 7. Starting the server
The following command starts the development server on port 5000.

```bash
poetry run flask run 
```

#### 8. Starting the celery worker
The following command starts Celery.

```bash
poetry run celery -A make_celery worker --loglevel=info --concurrency=3 --without-gossip --without-mingle -B -Q main,background -n w1@%h
# Celery runs until interrupted
```


More details in the [CLI](#CLI) and [API](#API) sections of this document.

[👆 Back to the summary](#summary)

---

## Configuration

The application's settings are defined globally using [Flask's configuration system](https://flask.palletsprojects.com/en/2.3.x/config/).

All available options listed detailed in [config.py](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/config.py).

[config.py](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/config.py) can be edited in place and used as-is, or replaced with another file / method of storing configuration data that Flask supports. 

Be sure to edit [`__init__.py` accordingly if you choose to use a different method of providing settings to Flask](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/__init__.py#L9).

By default, a small number of options can be replaced by an environment variable:
- ACCESS_KEY_SALT
- EXPOSE_SCOOP_LOGS
- DATABASE_*
- TEST_DATABASE_*
- API_DOMAIN
- VALIDATION_TIMEOUT
- BROKER_URL
- RESULT_BACKEND
- ENABLE_CELERY_BACKEND
- CELERYBEAT_TASKS
- SCOOP_PREFIX
- MAX_SUPPORTED_ARCHIVE_FILESIZE
- TEMPORARY_STORAGE_EXPIRATION
- VIDEO_ATTACHMENT_DOMAINS
- CUSTOM_USER_AGENT_DOMAINS

With few exceptions -- all related to input/output --, all of the [CLI options available for Scoop](https://github.com/harvard-lil/scoop#using-scoop-on-the-command-line) can be configured and tweaked in [config.py](https://github.com/harvard-lil/scoop-rest-api/blob/main/config.py).


[👆 Back to the summary](#summary)

---

## CLI

This application was built using [Flask](https://flask.palletsprojects.com/) for both its REST API and CLI components. 

Custom commands were created as a way to operate the application and administer it.  

<details>
    <summary><strong>Listing available commands</strong></summary>

```bash
poetry run flask --help`
# Sub-commands also have a help menu:
poetry run flask create-access-key --help
```
</details>

<details>
    <summary><strong>create-tables</strong></summary>

```bash
poetry run flask create-tables
```

Creates a new SQLite database if needed and populates it with tables. 
</details>

<details>
    <summary><strong>create-access-key</strong></summary>

```bash
poetry run flask create-access-key --label "John Doe"
```

Creates a new API access key. Said access key will only be displayed once, as a result of this command.
</details>

<details>
    <summary><strong>cancel-access-key</strong></summary>

```bash
poetry run flask cancel-access-key --id_access_key 1
```

Makes a given access key inoperable.
</details>

<details>
    <summary><strong>status</strong></summary>

```bash
poetry run flask status
```

Lists access key ids, as well as pending and started captures.
</details>


<details>
    <summary><strong>cleanup-local</strong></summary>

```bash
poetry run flask cleanup-local
```

Cleans up Scoop's temporary files.

Shelf-life is determined by `TEMPORARY_STORAGE_EXPIRATION` at [application configuration](#configuration) level.

This command should be run on a schedule everywhere Celery is deployed and running capture jobs.
</details>

<details>
    <summary><strong>cleanup-global</strong></summary>

```bash
poetry run flask cleanup-global
```

Removes _"expired"_ captures from the database, and finds and updates any failed
captures that were terminated without having their status recorded as "failed."

Shelf-life is determined by `TEMPORARY_STORAGE_EXPIRATION` at [application configuration](#configuration) level.

This command should be run on a schedule.

In multi-machine deployments, it should only be run on a single machine.
</details>

<details>
    <summary><strong>cleanup</strong></summary>

```bash
poetry run flask cleanup
```
Runs both `clean-local` and `cleanup-global`.

This command is most useful for single-machine deployments and local development.

For more complex deployments, separate use of `cleanup-local` and `cleanup-global` is recommended.
</details>

<details>
    <summary><strong>inspect-capture</strong></summary>

```bash
poetry run flask inspect-capture --id_capture "8130d6fe-4adb-4142-a685-00a64bb6ff29"
```

Returns full details about a given capture as JSON. Can be used by administrators to inspect logs.
</details>

[👆 Back to the summary](#summary)

---

## API

**Note:**
Unless specified otherwise, every capture-related object returned by the API is [generated using `capture_to_dict()`](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/utils/capture_to_dict.py).


<details>
    <summary><strong>[GET] /</strong></summary>

Simple _"ping"_ route to ensure the API is running.
Returns HTTP 200 and an empty body.
</details>

<details>
    <summary><strong>[POST] /capture</strong></summary>

Creates a capture request.

**Authentication:** Requires a valid access key, passed via the `Access-Key` header.

Accepts JSON body with the following properties:
- `url`: URL to capture (required)
- `callback_url`: URL to be called once capture is complete (optional). This URL will receive a JSON object describing the capture request and its current status.

Returns HTTP 200 and capture info.

The capture request will be rejected if the capture server is over capacity, as defined by the `MAX_PENDING_CAPTURES` setting in `config.py`.

**Sample request:**
```json
{
  "url": "https://lil.law.harvard.edu",
}
```

**Sample response:**
```json
{
  "callback_url": null,
  "created_timestamp": "Wed, 28 Jun 2023 16:30:28 GMT",
  "ended_timestamp": null,
  "follow": "https://scoop-rest-api.host/capture/5234bb37-58a8-4071-a65c-0f7815da5202",
  "id_capture": "5234bb37-58a8-4071-a65c-0f7815da5202",
  "started_timestamp": null,
  "status": "pending",
  "url": "https://lil.law.harvard.edu"
}
```

The `follow` property is a direct link to `[GET] /capture/<id_capture>`, described below.

</details>

<details>
    <summary><strong>[GET] /capture/&lt;id_capture&gt;</strong></summary>

Returns information about a specific capture.

**Authentication:** Requires a valid access key, passed via the `Access-Key` header. Access is limited to captures initiated using said access key.

**Sample response:**
```json
{
  "artifacts": [
    "https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/archive.wacz",
    "https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/provenance-summary.html",
    "https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/screenshot.png",
    "https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/lil.law.harvard.edu.pem",
    "https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/analytics.lil.tools.pem"
  ],
  "callback_url": null,
  "created_timestamp": "Wed, 28 Jun 2023 16:30:28 GMT",
  "ended_timestamp": "Wed, 28 Jun 2023 16:30:45 GMT",
  "id_capture": "2eb7145f-dd8e-4354-bf06-6afc6015c446",
  "started_timestamp": "Wed, 28 Jun 2023 16:30:30 GMT",
  "status": "success",
  "temporary_playback_url": "https://replayweb.page/?source=https://scoop-rest-api.host/artifact/2eb7145f-dd8e-4354-bf06-6afc6015c446/archive.wacz",
  "url": "https://lil.law.harvard.edu"
}
```

The entries under `artifacts` are direct links to `[GET] /artifact/<id_capture>/<filename>`.

`temporary_playback_url` allows for checking the resulting WACZ against [replayweb.page](https://replayweb.page).

</details>

<details>
    <summary><strong>[GET] /artifact/&lt;id_capture&gt;/&lt;filename&gt;</strong></summary>

Allows for accessing and downloading artifacts generated as part of the capture process.

This route is not access-controlled.

Files are only stored temporarily ([see `cleanup` CLI command](#cli)).
</details>

[👆 Back to the summary](#summary)

---

## Asynchronous tasks with Celery

We use [Celery](https://docs.celeryq.dev/en/stable/index.html) to run tasks
asynchronously, which is to say, outside the usual request/response flow of the
Flask application.

Tasks are defined in `scoop_rest_api/tasks.py`.

Tasks are put on a FIFO queue backed by redis/ElastiCache (configured by
`CELERY_SETTINGS["broker_url"]`), and are taken off the queue and processed by
Celery "workers": Linux processes that you spin up independently of the web
server. Each running task is effectively its own, short-lived instance of your
Flask application: you can access config, interact with models and
the database, etc.

To put a task on the queue, use the [`delay`]
(https://docs.celeryq.dev/en/stable/reference/celery.app.task.html?highlight=delay#celery.app.task.Task.delay)
or [`apply_async`]
(https://docs.celeryq.dev/en/stable/reference/celery.app.task.html?highlight=delay#celery.app.task.Task.apply_async)
methods. E.g.:

    my_task.delay()


The easiest way to start a worker locally is to set `START_CELERY=true` in docker-compose.yaml

````yaml
services:
  web:
    environment:
      # ...
      - START_CELERY=true
````

Then, a worker will be spun up by the container's docker entrypoint. To start one manually,
see docker-entrypoint.sh for an example invocation.

To schedule a task to run regularly, configure `CELERY_SETTINGS["beat_schedule"]`
with the desired schedule, route the task to an appropriate queue using
`CELERY_SETTINGS["task_routes"]` (or let it default to the main queue, which is
called 'celery'). Then, ensure that [celery beat is running]
(https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html#starting-the-scheduler),
and ensure that at least one worker is listening to the configured queue.


### Debugging Celery Tasks

For developers' convenience, Celery tasks can be run synchronously locally by
the Flask development server or in the Flask shell.

Set the `task_always_eager` setting to `True` in `config.py`:

```python
CELERY_SETTINGS = {
    # ...
    "task_always_eager": True
}
```

Then, when you call `my_task.delay()`, the task runs right there in the calling process,
as though you had invoked a "normal" python function rather than a celery task.

This not only reduces the amount of RAM/CPU utilized (because you don't need to
be running redis, and don't need to have any worker processes running), but
also makes it easy to drop into the debugger, and prints/logs to the console
like Flask does.

If `"task_always_eager": True`, you do not need to have a Celery worker running;
i.e., you don't need `START_CELERY=true`.


### Testing

The easiest way to test tasks is to call them directly in your test code:

    def test_my_task():
        my_task.run()

But, if you want to test with the full Celery apparatus (for instance, to check error handling and recovery, timeouts, etc.), a number of pytest fixtures are available. See the [Celery docs](https://docs.celeryq.dev/en/stable/userguide/testing.html) for further information.


[👆 Back to the summary](#summary)

---

## Deployment

Flask applications can be deployed in many different ways, therefore this section will focus mostly on what is specific about this project:
- The Flask application itself should be run using a production-ready WSGI server such as [gunicorn](https://gunicorn.org/), and ideally put [behind a reverse proxy](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04).
- The `start-parallel-capture-processes` command should run continually in a dedicated process.
- The `cleanup` command should be run on a scheduler, for example every 5 minutes.

### Running in headful mode
The default settings assume that [Scoop runs in headful mode](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/config.py#L88), which [generally yields better results](https://github.com/harvard-lil/scoop#should-i-run-scoop-in-headful-mode). 

Running in headful mode requires that a window system, if none is available:
- You may consider switching to headless mode (`--headless true`)
- Or use `xvfb-run` to provide a simulated X environment to the `start-parallel-capture-processes` command:
```bash
xvfb-run --auto-servernum -- flask start-parallel-capture-processes
```

### PostgreSQL over SSL
Using SSL when connecting to PostgreSQL is generally advised for security reasons, and should be enforced on the server side whenever possible.

To ensure that PostgreSQL connects over SSL, make sure to populate the `DATABASE_CA_PATH` environment variable appropriately to make it point to a certificate chain.

This project automatically pulls the latest Amazon RDS certificates as `./rds.pem`.

### Capture isolation

You may wish to set `SCOOP_PREFIX` in order to wrap the capture process in a tool like [firejail](https://firejail.wordpress.com/).

[👆 Back to the summary](#summary)

---

## Tests and linting

This project uses [pytest](https://docs.pytest.org/en/6.2.x/contents.html). 

The test suite creates _"throw-away"_ databases for the duration of the test session. 
It will try to use [default credentials](https://github.com/harvard-lil/scoop-rest-api/blob/main/scoop_rest_api/conftest.py) to do so, unless provided with test-specific credentials via the following environment variables:
- `TESTS_DATABASE_HOST`
- `TESTS_DATABASE_USERNAME`
- `TESTS_DATABASE_PASSWORD`
- `TESTS_DATABASE_PORT`

```bash
# Running tests in Docker
xvfb-run --auto-servernum -- poetry run pytest -v

# Running tests with a manual installation
poetry run pytest -v

# Run linter / formatter
poetry run black scoop_rest_api

# Bump app version
poetry version patch
```

[👆 Back to the summary](#summary)
