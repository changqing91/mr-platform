# 一键部署（Linux Ubuntu arm64）

仓库地址：<https://github.com/changqing91/mr-platform>

## 前置条件

- 已安装 Docker
- 服务器可访问外网以拉取基础镜像

## 快速部署

```bash
cd /Users/mujunhan/projects/what-tech/mr-platform
chmod +x deploy.sh
./deploy.sh
```

## 分模块部署

仅部署前端：
```bash
chmod +x deploy-frontend.sh
./deploy-frontend.sh
```

仅部署后端：
```bash
chmod +x deploy-server.sh
./deploy-server.sh
```

仅部署 tusd（数据卷映射到 /srv/mr/uploads）：
```bash
chmod +x deploy-tusd.sh
./deploy-tusd.sh
```

部署完成后访问：

- 前端：`http://<服务器IP>/`
- 后端管理：`http://<服务器IP>:1337/admin`

## Ubuntu 作为 SMB 服务器

在 Ubuntu 提供 SMB 共享（Windows 读共享）的场景下，按以下步骤配置：

1. 安装 Samba：
   ```bash
   sudo apt update
   sudo apt install -y samba
   ```
2. 创建共享目录与权限：
   ```bash
   sudo mkdir -p /mnt/upload
   sudo chown -R root:root /mnt/upload
   sudo chmod -R 0777 /mnt/upload
   ```
3. 配置共享（/etc/samba/smb.conf）：
   追加以下段落：
   ```ini
   [upload]
      path = /srv/mr/uploads
      browseable = yes
      read only = no
      guest ok = no
      create mask = 0666
      directory mask = 0777
   ```
4. 创建 Samba 用户并启用：
   ```bash
   # 先创建本地系统用户（二选一）
   sudo adduser admin
   # 或无家目录/禁止登录
   # sudo useradd -M -s /usr/sbin/nologin admin

   # 然后创建并启用 Samba 账户
   sudo smbpasswd -a admin
   sudo smbpasswd -e admin
   ```
5. 启动服务并放通防火墙（如启用 UFW）：
   ```bash
   sudo systemctl enable --now smbd nmbd
   sudo ufw allow samba
   ```
6. 验证端口连通性（Ubuntu 本机或其他主机）：
   ```bash
   nc -vz 192.168.1.224 445
   ```

Windows 客户端访问：
- 在资源管理器输入：`\\192.168.1.224\upload`，使用步骤 4 中的 `youruser`/密码登录

前端路径前缀（根据消费者操作系统选择）：
- 如果由 Windows 节点读取：建议 `VITE_TUSD_PATH_PREFIX=\\\\192.168.1.224\\upload\\`
- 如果由 Linux 节点读取：建议 `VITE_TUSD_PATH_PREFIX=/mnt/upload/` 或 `smb://192.168.1.224/upload/`

## 常用环境变量

```bash
FRONTEND_IMAGE=mr-frontend:arm64
SERVER_IMAGE=mr-server:arm64
TUSD_IMAGE=mr-tusd:arm64
NETWORK=mr-net

VITE_TUSD_ENDPOINT=/files
VITE_TUSD_PATH_PREFIX=\\\\192.168.1.224\\upload\\

TUSD_PORT=9000
TUSD_HOOK_PORT=3001
TUSD_UPLOAD_DIR=/data/uploads
TUSD_BASE_PATH=/files
UPLOADS_HOST_DIR=/mnt/upload
STRAPI_UPLOADS_HOST_DIR=/mnt/upload

APP_KEYS=change1,change2
API_TOKEN_SALT=change
ADMIN_JWT_SECRET=change
TRANSFER_TOKEN_SALT=change
JWT_SECRET=change
ENCRYPTION_KEY=change
```

示例：

```bash
APP_KEYS="k1,k2" JWT_SECRET="j" ADMIN_JWT_SECRET="a" ./deploy.sh
```
