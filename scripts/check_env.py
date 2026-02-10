#!/usr/bin/env python3
"""
IDM-GridCore 环境检查脚本
检查部署所需的环境条件
"""

import subprocess
import sys
import os
import socket


def check_command(cmd, name):
    """检查命令是否可用"""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, check=True)
        print(f"✓ {name} 已安装")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"✗ {name} 未安装")
        return False


def check_docker():
    """检查 Docker 是否可用"""
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Docker 已安装且运行中")
            return True
        else:
            if "permission denied" in result.stderr.lower():
                print("✗ Docker 权限不足（用户未在 docker 组）")
            else:
                print("✗ Docker 未运行")
            return False
    except FileNotFoundError:
        print("✗ Docker 未安装")
        return False


def check_port(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('localhost', port))
        if result == 0:
            print(f"✗ 端口 {port} 已被占用")
            return False
        else:
            print(f"✓ 端口 {port} 可用")
            return True


def check_rust():
    """检查 Rust 环境"""
    return check_command("cargo", "Rust/Cargo")


def check_redis_cli():
    """检查 redis-cli"""
    return check_command("redis-cli", "redis-cli")


def check_curl():
    """检查 curl"""
    return check_command("curl", "curl")


def get_architecture():
    """获取系统架构"""
    import platform
    machine = platform.machine()
    print(f"\n系统架构: {machine}")
    
    # 映射到 IDM-GridCore 的命名
    arch_map = {
        "x86_64": "linux-x64",
        "amd64": "linux-x64",
        "aarch64": "linux-arm64",
        "arm64": "linux-arm64",
        "armv7l": "linux-armv7"
    }
    
    mapped = arch_map.get(machine, machine)
    print(f"对应平台: {mapped}")
    return mapped


def main():
    print("=" * 50)
    print("IDM-GridCore 环境检查")
    print("=" * 50)
    
    all_ok = True
    
    # 检查基础工具
    print("\n【基础工具】")
    all_ok &= check_curl()
    
    # 检查 Docker
    print("\n【Docker 环境】")
    docker_ok = check_docker()
    all_ok &= docker_ok
    
    # 检查端口
    print("\n【端口检查】")
    port_8080_ok = check_port(8080)
    port_6379_ok = check_port(6379)
    
    # 检查可选工具
    print("\n【可选工具】")
    has_rust = check_rust()
    has_redis_cli = check_redis_cli()
    
    # 架构信息
    arch = get_architecture()
    
    # 总结
    print("\n" + "=" * 50)
    print("检查结果")
    print("=" * 50)
    
    if docker_ok and port_8080_ok and port_6379_ok:
        print("✓ 环境检查通过，可以部署 IDM-GridCore")
        print("\n推荐部署方式: 从零启动（本地快速部署）")
    else:
        print("✗ 环境检查未通过，请修复上述问题后再部署")
        if not docker_ok:
            print("\nDocker 问题解决方案:")
            print("  1. 安装 Docker: https://docs.docker.com/engine/install/")
            print("  2. 启动 Docker: sudo systemctl start docker")
            print("  3. 添加用户到 docker 组: sudo usermod -aG docker $USER")
        if not port_8080_ok or not port_6379_ok:
            print("\n端口占用解决方案:")
            print("  1. 更换端口部署")
            print("  2. 停止占用端口的进程")
        all_ok = False
    
    if not has_rust:
        print("\n注意: 未检测到 Rust 环境，将使用预编译二进制")
        print("如需本地编译，请安装 Rust: https://rustup.rs/")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
