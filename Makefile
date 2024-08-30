# Define the name of the Compose project
PROJECT_NAME := sensorguard

# Define default target
.PHONY: help
help:
    @echo "Available targets:"
    @echo "  up           - Start up the Docker Compose services".
    @echo "  down         - Stop and remove Docker Compose services"
    @echo "  build        - Build the Docker images"
    @echo "  logs         - View the logs of the Docker Compose services"
    @echo "  restart      - Restart the Docker Compose services"
    @echo "  shell        - Open a shell in the app container"
    @echo "  dbshell      - Open a shell in the database container"

.PHONY: up
up:
    sudo docker-compose -p $(PROJECT_NAME) up -d

.PHONY: down
down:
    docker-compose -p $(PROJECT_NAME) down

.PHONY: build
build:
    docker-compose -p $(PROJECT_NAME) build

.PHONY: logs
logs:
    docker-compose -p $(PROJECT_NAME) logs -f

.PHONY: restart
restart:
    docker-compose -p $(PROJECT_NAME) down
    docker-compose -p $(PROJECT_NAME) up -d

.PHONY: shell
shell:
    docker-compose -p $(PROJECT_NAME) exec app /bin/sh

.PHONY: dbshell
dbshell:
    docker-compose -p $(PROJECT_NAME) exec db /bin/sh
