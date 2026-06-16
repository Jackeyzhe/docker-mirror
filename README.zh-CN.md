# Docker Mirror Skill

[English](README.md)

Docker Mirror 是一个 Codex skill，用来处理 Docker Hub 镜像源失效或不可访问的问题。它会帮助 agent 查找当前可用的镜像源候选、实时探测可用性、安全生成 Docker daemon 配置变更，并在变更后验证 `docker pull` 是否恢复正常。

这个 skill 的默认策略偏谨慎：不内置长期镜像源列表，不静默修改 Docker 配置，也不会在没有确认的情况下重启 Docker。

## 功能

- 从实时来源或用户提供的 URL 收集当前 Docker Hub mirror 候选。
- 通过 `/v2/` 和小镜像 manifest 请求探测候选源。
- 以 dry-run 方式生成 `registry-mirrors` 的 Docker daemon JSON 变更。
- 只有明确传入写入参数时才修改配置。
- 覆盖已有 daemon JSON 前会创建备份。
- 保留 Docker daemon 中其它无关配置。
- 通过 `docker info` 和小镜像 `docker pull` 验证结果。

## 安装

使用 open skills CLI 安装：

```bash
npx skills add Jackeyzhe/docker-mirror --skill docker-mirror -g
```

也可以克隆仓库后，把 skill 目录复制到 Codex skills 目录：

```bash
git clone git@github.com:Jackeyzhe/docker-mirror.git
cp -R docker-mirror/docker-mirror ~/.codex/skills/docker-mirror
```

如果你使用 `skills-mgr` 管理 skills，请把 `~/.agents/skills` 作为源目录，然后同步：

```bash
cp -R docker-mirror/docker-mirror ~/.agents/skills/docker-mirror
skills-mgr sync
```

安装新 skill 后需要重启 Codex。

## 使用

让 Codex 使用这个 skill：

```text
Use $docker-mirror to find available Docker registry mirrors, update my Docker configuration safely, and verify docker pull.
```

预期流程：

1. 检查本地 Docker 环境。
2. 收集当前镜像源候选。
3. 探测候选源，只保留可用的 HTTPS mirror。
4. 生成 daemon JSON 的 dry-run 变更。
5. 写入配置或重启 Docker 前先让用户确认。
6. 用 `docker info` 和小镜像拉取验证结果。

## 脚本

### 探测镜像源候选

```bash
python3 docker-mirror/scripts/probe_mirrors.py \
  --candidate https://example-mirror.example.com \
  --image library/hello-world \
  --tag latest
```

从文件读取候选源：

```bash
python3 docker-mirror/scripts/probe_mirrors.py \
  --candidates-file mirrors.txt \
  --output json
```

默认拒绝 HTTP mirror。只有在明确接受 insecure registry 风险后，才使用 `--allow-http`。

### 修改 Docker daemon.json

只做 dry-run：

```bash
python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com
```

确认后写入：

```bash
sudo python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com \
  --write
```

使用 `--mode append` 保留已有 mirror 并追加新源；使用 `--mode replace` 用验证后的列表替换失效旧源。

## 平台说明

- Linux Docker Engine：默认使用 `/etc/docker/daemon.json`，除非 Docker 报告了其它 daemon 配置路径。
- Docker Desktop：优先通过 Settings -> Docker Engine 粘贴生成后的 JSON。除非你明确选择，否则不要编辑 Docker Desktop 的私有配置文件。

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests
```

校验 skill 结构：

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py docker-mirror
```

## 许可证

MIT
