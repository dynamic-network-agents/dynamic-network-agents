# Mac 上试跑参赛包的网络仿真、TX 和 RX

本指南针对当前工作区的 Apple Silicon Mac、Docker Desktop 和参赛包镜像。
已经确认 Docker 服务运行于 `linux/arm64`，三个参赛镜像为 `linux/amd64`。
本目录提供单独的 Compose 试跑配置；完整场景和业务收发仍需要完成下面的运行验证。
2026-11-11 已在临时容器中验证本机 OVS 内核网桥、veth 和 netem 可用。
镜像中的旧服务脚本误将内置 OVS 支持判成需要加载模块，现由本目录的启动适配脚本处理。
诊断时没有启动完整场景或 TX/RX，也没有修改 Docker Desktop 设置。

## 先理解几个名称

- **镜像（Image）**：打包的软件及依赖；参赛包中的 `.tar` 是镜像归档。
- **容器（Container）**：从镜像启动出来的运行实例。
- **Docker Desktop**：在 Mac 上提供运行 Linux 容器的虚拟机和管理界面。
- **Compose**：用一个 YAML 文件描述几个容器的配置和关联。
- **挂载（volume/bind mount）**：让容器访问 Mac 上的目录。本配置会把参赛包的 conf/data/assets/logs 提供给容器；运行时会更新配置和日志。
- **TX / RX**：业务发送端 / 业务接收端。这里需要把它们接入 netsim 建立的虚拟网络。

`linux/amd64` 转译可以帮助执行 x86 程序，但不会提供一个新的 x86 Linux 内核。
当前 `6.10.14-linuxkit` 内核配置显示 OVS、veth、netem 已内置；也已通过实际创建测试。
下面的检查使用修正后的启动方式，不再调用旧服务脚本去执行 modprobe/rmmod。

## 1. 打开 Docker Desktop 和终端

保持 Docker Desktop 处于运行状态。在 macOS 的“终端”或 IDE 终端中执行所有命令。
不需要先进入某个容器，也不需要在 Mac 上使用 `sudo docker`。

```bash
cd "/Volumes/APFS2/dynamic-network-agents"
docker version
docker compose version
```

`docker version` 应同时显示 Client 和 Server；只有 Client 或出现无法连接 daemon，说明 Docker 服务未就绪。
当前已经查询到 Docker Desktop 4.46.0、Engine 28.4.0、Compose v2.39.2。

在 Docker Desktop 的 Settings 中检查：

- General：使用 Apple Virtualization framework 时，可启用 “Use Rosetta for x86_64/amd64 emulation on Apple Silicon”，以加速 x86 用户态转译。选项名称随版本可能略有区别。修改后需要 Apply & restart。
- Resources → File sharing：确保 `/Volumes/APFS2/dynamic-network-agents` 可共享。如果默认已经共享 `/Volumes`，不必重复添加。
- Resources → Advanced：小场景可以先用现有资源配置。若机器有至少 16 GB 内存，可把 Docker 内存设为约 8 GB、CPU 设为 4 核作为试跑起点；这不是赛题给出的最低要求。不要把主机全部资源分给 Docker。

## 2. 导入三个镜像

下面三条命令将包内归档导入 Docker，不会启动仿真。

```bash
docker load -i "仿真环境-参赛包/simulator/images/netsim.tar"
docker load -i "仿真环境-参赛包/simulator/images/servicesim-tx.tar"
docker load -i "仿真环境-参赛包/simulator/images/servicesim-rx.tar"
```

成功时分别包含：

```text
Loaded image: netsim:latest
Loaded image: servicesim-tx:latest
Loaded image: servicesim-rx:latest
```

检查：

```bash
docker image ls netsim
docker image ls servicesim-tx
docker image ls servicesim-rx
```

Docker Desktop 的 Images 页面也能看到它们。暂时不导入测评和模型网关镜像。

## 3. 检查 x86 程序与虚拟网络能力

先确认镜像里的 Python 能运行：

```bash
docker run --rm --platform linux/amd64 --entrypoint /bin/bash netsim:latest -lc 'python3 --version'
```

这条命令创建一个临时容器，运行完自动删除。出现 Python 版本号只说明用户态程序能执行，还没有建立网络。

再执行下面这条命令。它会创建一个临时容器，在该容器的网络命名空间中测试 OVS、虚拟网卡和 netem。
仅只读挂载本地启动脚本，不挂载场景、配置、素材或日志，不发布端口，不使用 host 网络；`--privileged` 是为了操作虚拟网络。
请确保终端仍在项目根目录。

```bash
docker run --rm --platform linux/amd64 --privileged \
  --mount "type=bind,src=$PWD/mac-docker-trial/start-netsim.sh,dst=/opt/mac-trial/start-netsim.sh,readonly" \
  --entrypoint /bin/bash netsim:latest \
  /opt/mac-trial/start-netsim.sh --check
```

需要看到正常的 OVS datapath 信息、包含 `netem` 的队列输出，以及最后的 `NETWORK_PROBE_OK`。
这只验证基础网络功能，完整场景还要继续检查。

旧检查出现的 `Module openvswitch not found` 和随后 `ovs-vsctl` 超时，已定位为服务启动兼容问题。
不要重新执行旧版 `service openvswitch-switch start` 检查，使用上面的适配脚本。

**如果使用新检查仍出现 datapath、Operation not permitted、Operation not supported、Exec format error 或 Rosetta 错误，先停在这里，保留完整输出。**
不要因为 Python 可以运行就继续等待完整场景。缺少内核功能和缺少/不可见模块文件需要分别判断，不能单凭一个 `modprobe` 报错就认定 Mac 永远无法运行。
本配置没有把 Mac 的 `/lib/modules` 挂进容器：Mac 并没有一个可供这个 Linux 内核使用的原生 `/lib/modules`。

## 4. 只启动 netsim，等待建网完成

每个新开的终端都先回到工作区根目录：

```bash
cd "/Volumes/APFS2/dynamic-network-agents"
docker compose -f mac-docker-trial/compose.yml config --quiet
docker compose -f mac-docker-trial/compose.yml up -d netsim
docker compose -f mac-docker-trial/compose.yml logs -f netsim
```

- `-f` 指定本次使用的配置文件。
- `up -d netsim` 只启动网络仿真模块，`-d` 表示后台运行。
- `logs -f` 持续显示日志。按 `Ctrl+C` 只是退出日志查看，不会停止后台容器。

配置已选定包内最小场景 `sce20261031-conf02 / sce01`：20 节点、30 链路、40 业务。
镜像入口会先建网，然后启动界面并生成节点表。这个阶段不需要 TX/RX 已经启动。

需要等待类似 `[start] 就绪 ... 节点表 conf/sim-nodes.json` 的成功消息。小场景也可能需要几分钟，ARM 转译下可能更慢。
如果日志只是在等待，另开终端查看实际建网日志：

```bash
cd "/Volumes/APFS2/dynamic-network-agents"
docker compose -f mac-docker-trial/compose.yml exec -T netsim \
  tail -n 100 /opt/simulator/logs/run/start-netsim.log
```

不要把“冷启动就绪（空网态）”当成场景已建成。运行镜像在建网失败后有退回空网的逻辑；UI 能打开也不足以证明成功。

打开浏览器：

```text
http://localhost:10000
```

确认实际选择的是上述套件和场景，能看到对应拓扑、节点和链路。
此时先不开始计时测试，先完成 TX/RX 就绪。

## 5. 启动 TX 和 RX

网络已经建成后执行：

```bash
docker compose -f mac-docker-trial/compose.yml up -d tx rx
docker compose -f mac-docker-trial/compose.yml ps
docker compose -f mac-docker-trial/compose.yml logs -f tx rx
```

TX/RX 与 netsim 共享网络和进程可见范围，按节点表把业务进程接入虚拟节点。
查找“业务仿真就绪”、`N/N ... ready` 等就绪信息，确认没有找不到启动文件、注入失败或目标不可达。
如果容器立刻退出，用 `docker compose -f mac-docker-trial/compose.yml ps -a` 看状态并保留日志。

本配置同时映射了 TX/RX 自带的总览页：

```text
发送端：http://localhost:10001
接收端：http://localhost:10002
```

这些页面与容器日志可辅助排查，仍然以实际收发统计确认流量。
前端刚刚启动、只有监听端口、容器显示 Running，都不能单独证明业务已经开始。

这两个页面来自参赛镜像内的 `servicesim/bin/frontend.py`，不是本试跑目录编写的页面。
本配置额外映射了 10001/10002；包内原版 netsim Compose 没有映射这两个端口，所以其他人的浏览器打不开它们，不足以说明 TX/RX 未启动。
TX 页会查询每个节点的 `http://<节点IP>:8090/api/v1/services/health`；RX 页对应 8092。
`down(URLError)` 表示页面后端访问节点健康接口失败，单看这一文字不能区分连接被拒绝、超时等原因，也不是业务丢包率。

**切换场景或重新建网后全部变成 `down(URLError)`：**

2026-11-11 本机遇到过这种情况：旧业务进程在拆网时被清理，页面进程仍在；新网络和节点表已生成，但镜像入口没有自动重新注入业务进程。
原版 Compose 和运行日志虽然提到 watcher，本包实际镜像入口仍是一次性注入。
等待日志出现“节点表已刷新”或确认新网络建好，再执行：

```bash
docker compose -f mac-docker-trial/compose.yml restart tx rx
docker compose -f mac-docker-trial/compose.yml logs --since=2m -f tx rx
```

这里要用 `restart`：对已经运行的容器再次执行 `up -d tx rx` 通常不会重新执行启动脚本。
确认两端输出新的 `N/N ... ready`，再刷新 10001/10002。
如果主界面正在等待“业务仿真服务在线”，就绪后可能继续刚才的启动请求，无需反复点击“开始”。
恢复健康检查只代表业务进程可访问，实际收发还需要下一步验证。

## 6. 从仿真界面启动一次测试

回到 `http://localhost:10000`，保持：

- 场景套件：`sce20261031-conf02`
- 场景：`sce01`
- 脚本：`script-01`

使用界面中的启动操作发起测试，观察本次实例标识和 T0。
文档没有附完整界面截图；以实际按钮文字和当前状态为准。如果开始操作提示业务未就绪，先检查上一步的 TX/RX 日志。
若这次操作触发了网络重建，并停在等待外部业务实例，按第 5 步在节点表刷新后重启 TX/RX。

第一次试跑先观察这些结果：

1. 测试实例确实开始，运行时间推进。
2. 业务有当前路径，发送记录持续更新。
3. 接收端收到数据，接收计数或有效带宽不为零；不要求所有业务在资源不足时都达到需求。
4. 业务详情的最近 1 秒 `actual` 统计更新。公开接口为 `GET /api/open/v1/services/{serviceId}`，`effBwBps` 是其中一个指标；界面未显示足够数据时，需进一步通过该接口核对。
5. 本次实例的日志出现在 `仿真环境-参赛包/simulator/logs/<套件>/<场景>/<脚本>/<实例>/` 下，注意区分新实例与历史日志。

当前脚本带 `time=1800` 的 stop，即完整测试为 30 分钟。只观察收发是否开始，无需等满 30 分钟；结束试跑时先使用界面的停止操作，再停止容器。

更完整的检查应选择确实经过事件链路的业务，对照事件、路径和接收指标的变化。某次断链没有影响某条业务，可能是它本来就没走那条链路，或者系统已经自动重算路线。

## 7. 查看、停止和重新启动

```bash
docker compose -f mac-docker-trial/compose.yml ps -a
docker compose -f mac-docker-trial/compose.yml logs --tail=100 netsim tx rx
```

停止并移除本次配置的三个容器：

```bash
docker compose -f mac-docker-trial/compose.yml down
```

这不会删除镜像，也不会删除挂载到 Mac 上的场景、配置和日志。
网络拆除有最长 90 秒的正常退出等待，不要立即反复点击启动。

下次启动仍按顺序执行：先 `up -d netsim`，确认建网就绪，再 `up -d tx rx`。
本包实际 TX/RX 镜像入口是一次性注入，不能仅凭外层 compose 注释假定它会自动跟随重建。
首次先固定同一套件/场景；更换场景或重建 netsim 后，需要重新启动 TX/RX，并重新验证就绪。

## 本配置为什么和包内原版不同

- 显式指定 `platform: linux/amd64`，对应提供的镜像架构。
- `start-netsim.sh` 直接启动 OVS 数据库和转发进程，并适配原入口对 `service openvswitch-switch start` 的重复调用，避免旧脚本误执行 modprobe/rmmod。随后运行原镜像入口，原厂文件不需要修改。
- 使用外部 TX/RX 注入模式，netsim 环境设置 `SIM_CONF_EXTERNAL=1`。
- 只挂载 conf/data/assets/logs。包内 TX/RX compose 指向的宿主 `servicesim/` 目录不存在，直接挂载会遮住镜像中已有程序。
- 不运行原版的 fixperm 初始化服务：镜像中的入口已有执行权限，那个服务针对宿主代码树操作。
- 不挂载 Mac 的 `/lib/modules`。这不是补齐 Linux 内核功能的办法；是否可运行以第 3 步和实际建网为准。
- 先不启动测评、大模型网关和跨机器媒体中继，保持单机注入方式。

如果底层兼容检查失败，先提供检查输出再决定下一步。在只有 Mac 的条件下，完整 x86 Linux 虚拟机是可能的后续路线，但不等于普通 ARM Ubuntu 虚拟机，运行性能与时间评估也需重新核验。

## 参考

- 参赛包：`doc/仿真环境使用说明.md`、`doc/仿真软件接口.md`。
- Docker Desktop 设置：https://docs.docker.com/desktop/settings-and-maintenance/settings/
- Docker VMM 与 Rosetta：https://docs.docker.com/desktop/features/vmm/
- bind mount 覆盖行为：https://docs.docker.com/engine/storage/bind-mounts/
- 多架构与共享内核：https://docs.docker.com/build/building/multi-platform/
