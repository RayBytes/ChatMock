# ChatMock Documentation

Welcome to the ChatMock documentation! This directory contains comprehensive guides for deploying, configuring, and using ChatMock.

## 📚 Documentation Index

### Getting Started
- **[Main README](../README.md)** - Project overview and quick start guide
- **[.env.example](../.env.example)** - Configuration options reference

### Features
- **[WEBUI.md](./WEBUI.md)** - Web dashboard documentation
  - Dashboard overview
  - Usage statistics and monitoring
  - Model information
  - Configuration management
  - API endpoints

### Deployment
- **[PRODUCTION.md](./PRODUCTION.md)** - Production deployment guide
  - Gunicorn configuration
  - Performance tuning
  - Scaling strategies
  - Monitoring and logging
  - High availability setup
  - Security best practices

- **[TRAEFIK.md](./TRAEFIK.md)** - Traefik integration guide
  - Automatic HTTPS with Let's Encrypt
  - Reverse proxy configuration
  - Load balancing
  - Custom middleware
  - Troubleshooting

## 🚀 Quick Links

### Common Tasks

**Deploy with Docker:**
```bash
docker-compose up -d
```

**Deploy with Traefik (HTTPS):**
```bash
docker-compose -f docker-compose.traefik.yml up -d
```

**Access WebUI:**
- Local: http://localhost:8000/webui
- Production: https://your-domain.com/webui

**First-time login:**
```bash
docker-compose --profile login up chatmock-login
```

## 📖 Documentation Structure

```
docs/
├── README.md          # This file
├── WEBUI.md          # Web dashboard guide
├── PRODUCTION.md     # Production deployment
└── TRAEFIK.md        # Traefik integration
```

## 🔧 Configuration

Key configuration files:
- `.env` - Environment variables (copy from `.env.example`)
- `gunicorn.conf.py` - Gunicorn server configuration
- `docker-compose.yml` - Standard Docker deployment
- `docker-compose.traefik.yml` - Traefik-integrated deployment

## 🆕 New in This Release

### Performance Improvements
- ✅ **Gunicorn with gevent workers** - 3-5x performance increase
- ✅ **Concurrent request handling** - Handle 1000+ connections
- ✅ **Production-ready deployment** - Battle-tested WSGI server

### WebUI Dashboard
- ✅ **Real-time statistics** - Monitor usage and limits
- ✅ **Visual analytics** - Charts and progress bars
- ✅ **Configuration management** - Change settings via UI
- ✅ **Model browser** - Explore available models

### Traefik Integration
- ✅ **Automatic HTTPS** - Let's Encrypt certificates
- ✅ **Reverse proxy** - Production-ready routing
- ✅ **Load balancing** - Scale horizontally
- ✅ **Health monitoring** - Automatic health checks

## 🎯 Use Cases

### Development
Perfect for local development with OpenAI-compatible APIs:
```bash
# Start server
docker-compose up -d

# Use with any OpenAI-compatible client
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Production
Deploy with Traefik for automatic HTTPS:
```bash
# Configure domain in .env
CHATMOCK_DOMAIN=chatmock.example.com

# Deploy
docker-compose -f docker-compose.traefik.yml up -d

# Access via HTTPS
curl https://chatmock.example.com/health
```

### High Availability
Scale horizontally for high-traffic scenarios:
```bash
# Scale to 5 instances
docker-compose up -d --scale chatmock=5

# Load balancing handled automatically by Traefik
```

## 🔍 Troubleshooting

### Common Issues

**WebUI not loading?**
- Check server is running: `docker-compose ps`
- Verify port 8000 is accessible
- Review logs: `docker-compose logs chatmock`

**Performance issues?**
- Increase Gunicorn workers: `GUNICORN_WORKERS=8`
- Check resource limits: `docker stats chatmock`
- See [PRODUCTION.md](./PRODUCTION.md) for tuning guide

**SSL certificate issues?**
- Verify DNS points to server
- Check Traefik logs: `docker logs traefik`
- See [TRAEFIK.md](./TRAEFIK.md) for troubleshooting

## 📊 Performance Benchmarks

With Gunicorn + gevent (4 CPU cores, 8GB RAM):

| Metric | Value |
|--------|-------|
| Requests/Second | 200-500+ |
| Concurrent Connections | 1000+ |
| Average Latency | 50-80ms |
| Memory per Worker | ~150MB |

See [PRODUCTION.md](./PRODUCTION.md) for detailed benchmarks.

## 🛡️ Security

Security features:
- OAuth2 authentication with ChatGPT
- HTTPS/TLS encryption (with Traefik)
- Network isolation
- Resource limits
- Non-root container execution
- Secrets management support

See [PRODUCTION.md](./PRODUCTION.md) for security best practices.

## 🤝 Contributing

Found an issue or want to improve the documentation?
1. Fork the repository
2. Make your changes
3. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## 📝 License

See [LICENSE](../LICENSE) file for license information.

## 🔗 Additional Resources

- **GitHub Repository**: https://github.com/RayBytes/ChatMock
- **Issue Tracker**: https://github.com/RayBytes/ChatMock/issues
- **Discussions**: https://github.com/RayBytes/ChatMock/discussions

## 💡 Tips

1. **Start simple**: Use `docker-compose.yml` for local development
2. **Go production**: Switch to `docker-compose.traefik.yml` for deployment
3. **Monitor usage**: Check WebUI dashboard regularly
4. **Tune performance**: Adjust Gunicorn workers based on load
5. **Enable HTTPS**: Always use Traefik in production
6. **Scale horizontally**: Add more instances as traffic grows
7. **Backup data**: Regular backups of `/data` volume
8. **Update regularly**: Pull latest images for security updates

## 📧 Support

Need help?
- Check documentation in this directory
- Search [GitHub Issues](https://github.com/RayBytes/ChatMock/issues)
- Create a new issue with detailed information
- Join community discussions

---

**Happy deploying! 🚀**
