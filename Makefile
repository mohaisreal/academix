.PHONY: help dev-up dev-down dev-logs dev-build dev-rebuild prod-up prod-down prod-logs prod-build prod-rebuild backend-shell frontend-shell migrate collectstatic clean

# Salida con color
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Comandos de Docker Compose
DOCKER_COMPOSE_DEV := docker compose --env-file .env.dev -f docker-compose.dev.yml
DOCKER_COMPOSE_PROD := docker compose --env-file .env.prod -f docker-compose.prod.yml

help:
	@echo "$(CYAN)Academix Docker Deployment - Available Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Development Environment:$(NC)"
	@echo "  make dev-up              - Start development containers"
	@echo "  make dev-down            - Stop development containers"
	@echo "  make dev-logs            - Tail logs from development containers"
	@echo "  make dev-build           - Build development images"
	@echo "  make dev-rebuild         - Rebuild development images (no cache)"
	@echo "  make backend-shell       - Open bash shell in running backend container"
	@echo "  make frontend-shell      - Open bash shell in running frontend container"
	@echo "  make migrate             - Run Django migrations in dev backend"
	@echo ""
	@echo "$(GREEN)Production Environment:$(NC)"
	@echo "  make prod-up             - Start production containers"
	@echo "  make prod-down           - Stop production containers"
	@echo "  make prod-logs           - Tail logs from production containers"
	@echo "  make prod-build          - Build production images"
	@echo "  make prod-rebuild        - Rebuild production images (no cache)"
	@echo "  make prod-migrate        - Run Django migrations in prod backend"
	@echo "  make prod-createsuperuser - Create Django superuser in prod"
	@echo ""
	@echo "$(GREEN)Django Utilities:$(NC)"
	@echo "  make migrate             - Run Django migrations (dev)"
	@echo "  make collectstatic       - Collect static files (dev)"
	@echo "  make createsuperuser     - Create Django superuser (dev)"
	@echo ""
	@echo "$(GREEN)Maintenance:$(NC)"
	@echo "  make clean               - Remove all containers and images"
	@echo "  make help                - Show this help message"
	@echo ""

# ============================================================================
# Comandos de desarrollo
# ============================================================================

dev-up:
	@echo "$(CYAN)Starting development environment...$(NC)"
	$(DOCKER_COMPOSE_DEV) up -d
	@echo "$(GREEN)Development environment started!$(NC)"
	@echo ""
	@echo "$(CYAN)Services:$(NC)"
	@echo "  Frontend:  http://localhost:4321"
	@echo "  Backend:   http://localhost:8000"
	@echo "  API:       http://localhost:8000/api/"
	@echo ""

dev-down:
	@echo "$(CYAN)Stopping development environment...$(NC)"
	$(DOCKER_COMPOSE_DEV) down
	@echo "$(GREEN)Development environment stopped!$(NC)"

dev-logs:
	@echo "$(CYAN)Tailing logs from development containers (Ctrl+C to exit)...$(NC)"
	$(DOCKER_COMPOSE_DEV) logs -f --tail=50

dev-build:
	@echo "$(CYAN)Building development images...$(NC)"
	$(DOCKER_COMPOSE_DEV) build
	@echo "$(GREEN)Development images built!$(NC)"

dev-rebuild:
	@echo "$(CYAN)Rebuilding development images (no cache)...$(NC)"
	$(DOCKER_COMPOSE_DEV) build --no-cache
	@echo "$(GREEN)Development images rebuilt!$(NC)"

# ============================================================================
# Comandos de producción
# ============================================================================

prod-up:
	@echo "$(CYAN)Starting production environment...$(NC)"
	$(DOCKER_COMPOSE_PROD) up -d
	@echo "$(GREEN)Production environment started!$(NC)"
	@echo ""
	@echo "$(CYAN)Services:$(NC)"
	@echo "  Frontend:  http://localhost"
	@echo "  Backend:   http://localhost:8000"
	@echo "  API:       http://localhost/api/"
	@echo ""

prod-down:
	@echo "$(CYAN)Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE_PROD) down
	@echo "$(GREEN)Production environment stopped!$(NC)"

prod-logs:
	@echo "$(CYAN)Tailing logs from production containers (Ctrl+C to exit)...$(NC)"
	$(DOCKER_COMPOSE_PROD) logs -f --tail=50

prod-build:
	@echo "$(CYAN)Building production images...$(NC)"
	$(DOCKER_COMPOSE_PROD) build
	@echo "$(GREEN)Production images built!$(NC)"

prod-rebuild:
	@echo "$(CYAN)Rebuilding production images (no cache)...$(NC)"
	$(DOCKER_COMPOSE_PROD) build --no-cache
	@echo "$(GREEN)Production images rebuilt!$(NC)"

prod-migrate:
	@echo "$(CYAN)Running Django migrations in production backend...$(NC)"
	$(DOCKER_COMPOSE_PROD) exec backend python manage.py migrate
	@echo "$(GREEN)Migrations completed!$(NC)"

prod-createsuperuser:
	@echo "$(CYAN)Creating Django superuser in production backend...$(NC)"
	$(DOCKER_COMPOSE_PROD) exec backend python manage.py createsuperuser

# ============================================================================
# Acceso a shells de contenedor
# ============================================================================

backend-shell:
	@echo "$(CYAN)Opening bash shell in backend container...$(NC)"
	$(DOCKER_COMPOSE_DEV) exec backend bash

frontend-shell:
	@echo "$(CYAN)Opening bash shell in frontend container...$(NC)"
	$(DOCKER_COMPOSE_DEV) exec frontend bash

# ============================================================================
# Comandos de administración de Django
# ============================================================================

migrate:
	@echo "$(CYAN)Running Django migrations...$(NC)"
	$(DOCKER_COMPOSE_DEV) exec backend python manage.py migrate
	@echo "$(GREEN)Migrations completed!$(NC)"

collectstatic:
	@echo "$(CYAN)Collecting static files...$(NC)"
	$(DOCKER_COMPOSE_DEV) exec backend python manage.py collectstatic --noinput
	@echo "$(GREEN)Static files collected!$(NC)"

createsuperuser:
	@echo "$(CYAN)Creating Django superuser...$(NC)"
	$(DOCKER_COMPOSE_DEV) exec backend python manage.py createsuperuser

# ============================================================================
# Comandos de mantenimiento
# ============================================================================

clean:
	@echo "$(RED)Removing all containers and images...$(NC)"
	@read -p "Are you sure? This will delete all data. (y/N) " confirm; \
	if [ "$$confirm" = "y" ]; then \
		$(DOCKER_COMPOSE_DEV) down -v --remove-orphans; \
		$(DOCKER_COMPOSE_PROD) down -v --remove-orphans; \
		docker system prune -f; \
		echo "$(GREEN)Cleanup completed!$(NC)"; \
	else \
		echo "$(YELLOW)Cleanup cancelled.$(NC)"; \
	fi

# ============================================================================
# Comandos de estado e información
# ============================================================================

status-dev:
	@echo "$(CYAN)Development Environment Status:$(NC)"
	$(DOCKER_COMPOSE_DEV) ps

status-prod:
	@echo "$(CYAN)Production Environment Status:$(NC)"
	$(DOCKER_COMPOSE_PROD) ps

ps-dev: status-dev

ps-prod: status-prod
