# MetaClaw 服务器部署检查清单

## 部署前准备

- [ ] 服务器系统：Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- [ ] 内存：至少 2GB RAM（推荐 4GB）
- [ ] 磁盘：至少 20GB 可用空间
- [ ] 网络：开放端口 9899（或配置 Nginx）
- [ ] 域名：（可选，用于 HTTPS）

## 部署步骤

### Docker 部署（推荐）

1. [ ] 安装 Docker 和 Docker Compose
   ```bash
   curl -fsSL https://get.docker.com | bash
   ```

2. [ ] 下载部署脚本
   ```bash
   curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/cloud-deploy.sh | bash
   ```

3. [ ] 配置环境变量
   ```bash
   cd /opt/metaclaw
   cp .env.example .env
   nano .env
   ```

4. [ ] 填入必要配置
   - [ ] API Key（必填）
   - [ ] 渠道类型（weixin/feishu/dingtalk/qq）
   - [ ] AI 模型选择
   - [ ] Web 密码（可选）

5. [ ] 启动服务
   ```bash
   docker-compose up -d
   ```

6. [ ] 验证运行状态
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

### 传统部署

1. [ ] 安装依赖（Python 3.7-3.12, git, nodejs）
2. [ ] 运行安装脚本
3. [ ] 配置 config.json
4. [ ] 使用 systemd 管理服务
5. [ ] 配置 Nginx 反向代理（推荐）

## 安全配置

- [ ] 设置 Web 控制台密码
- [ ] 配置防火墙规则
- [ ] 启用 HTTPS（Let's Encrypt）
- [ ] 定期备份 workspace 数据
- [ ] 配置日志轮转

## 监控告警

- [ ] 设置服务健康检查
- [ ] 配置磁盘空间监控
- [ ] 设置内存使用告警
- [ ] 配置日志异常告警

## 维护任务

- [ ] 每周更新检查：`metaclaw-update`
- [ ] 每月备份数据
- [ ] 每季度安全审计
- [ ] 监控 API Key 使用情况

## 故障排查

### 服务无法启动

1. 检查日志：`docker-compose logs`
2. 检查端口占用：`netstat -tlnp | grep 9899`
3. 检查配置：`cat .env`

### Web 控制台无法访问

1. 检查防火墙：`ufw status`
2. 检查 Nginx：`nginx -t`
3. 检查服务状态：`docker-compose ps`

### API 调用失败

1. 检查 API Key 有效性
2. 检查网络连接
3. 查看应用日志

## 升级步骤

1. [ ] 备份当前数据
   ```bash
   cp -r workspace workspace-backup-$(date +%Y%m%d)
   ```

2. [ ] 拉取最新镜像
   ```bash
   docker-compose pull
   ```

3. [ ] 重启服务
   ```bash
   docker-compose up -d
   ```

4. [ ] 验证升级成功
   ```bash
   docker-compose logs --tail=50
   ```

## 回滚步骤

1. [ ] 停止服务
   ```bash
   docker-compose down
   ```

2. [ ] 恢复备份
   ```bash
   rm -rf workspace
   cp -r workspace-backup-YYYYMMDD workspace
   ```

3. [ ] 启动服务
   ```bash
   docker-compose up -d
   ```

## 联系支持

- GitHub Issues：https://github.com/WarholYuan/MetaClaw/issues
- 文档中心：https://docs.metaclaw.ai/
- 社区交流：https://link-ai.tech/metaclaw/create
