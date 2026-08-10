# Deployment & Security Checklist

## Before Going to Production

### Environment Variables (.env)
- [ ] Update `DJANGO_SECRET_KEY` to a new random value (minimum 50 characters)
- [ ] Update `POSTGRES_PASSWORD` to a strong password (minimum 20 characters)
- [] Set `DEBUG=False` 
- [ ] Set `ALLOWED_HOSTS` to your production domain(s)
- [ ] Update `CSRF_TRUSTED_ORIGINS` to match your domain

### Database Security
- [ ] Change default PostgreSQL credentials in `.env`
- [ ] Consider using a separate database user with limited privileges
- [ ] Back up the `postgres_data` volume before production deployment
- [ ] Consider enabling PostgreSQL SSL connections (require `sslmode=require`)

### Docker Security
- [ ] Use specific image versions (already using `postgres:17-alpine`, `redis:7-alpine`)
- [ ] Never expose PostgreSQL port 5432 to the public internet
- [ ] Use a firewall to restrict access to port 8000 (web)
- [ ] Consider using a reverse proxy (nginx/caddy) with SSL/TLS

### Django Settings
- [ ] Set `SESSION_COOKIE_SECURE=True` in production
- [ ] Set `CSRF_COOKIE_SECURE=True` in production
- [ ] Use HTTPS only (`SECURE_SSL_REDIRECT=True`)
- [ ] Set `SECURE_HSTS_SECONDS=31536000` for HSTS

### Data Persistence
- [ ] Volume is set up: `event-finder_postgres_data`
- [ ] Volume driver: local (suitable for single-host deployments)
- [ ] Current size: Monitor with `docker volume inspect`
- [ ] Backup strategy: Use `docker compose exec db pg_dump` or third-party tools

### Backup Strategy
```bash
# Backup PostgreSQL data
docker compose exec db pg_dump -U django_user django_db > backup.sql

# Or backup the entire volume
docker run --rm -v event-finder_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_data.tar.gz -C /data .
```

### Running the App
```bash
# Development
./run.sh

# Stop services
docker compose down

# View logs
docker compose logs -f web

# SSH into web container for debugging
docker compose exec web bash
```

## Networking
- Services use isolated bridge network: `app-network`
- PostgreSQL is NOT exposed externally by default (only to web service)
- Only web service (port 8000) and db port (5432) are exposed

## Restore from Backup
```bash
# Restore PostgreSQL backup
docker compose exec -T db psql -U django_user django_db < backup.sql

# Restore volume backup
docker run --rm -v event-finder_postgres_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_data.tar.gz -C /data
```

## Static Files Management

### Automatic Collection
Static files are automatically collected when the container starts:
- Runs: `python manage.py collectstatic --noinput`
- Output volume: `event-finder_staticfiles`
- Size: Monitor with `docker volume inspect event-finder_staticfiles`

### Rebuild Staticfiles (after adding new static assets)
Option 1 - Restart the container (triggers collectstatic automatically):
```bash
docker compose restart web
```

Option 2 - Run manually:
```bash
docker compose exec web python manage.py collectstatic --noinput
```

### Serving Static Files in Production
For production, use a reverse proxy (nginx/caddy) to serve static files from the volume:

Example nginx configuration:
```nginx
upstream web {
    server web:8000;
}

server {
    listen 80;
    client_max_body_size 10M;

    location /static/ {
        alias /staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /media/;
        expires 7d;
    }

    location / {
        proxy_pass http://web;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then add to docker-compose.yml:
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - event-finder_staticfiles:/staticfiles:ro
      - event-finder_media:/media:ro
    depends_on:
      - web
```

### Volume Cleanup
Remove old staticfiles (when resetting for development):
```bash
docker volume rm event-finder_staticfiles
```
