#!/usr/bin/env python3
"""
代码上下文生成器
----------------
将 pyreverse 生成的 PlantUML 文件转换为 AI 友好的文本摘要，
供 Kimi / Claude 等助手在编码时快速理解项目结构。

用法:
    python scripts/generate_code_context.py

依赖:
    pip install pylint  # 提供 pyreverse

输出:
    .kimi/code-context/
    ├── module_deps.md      # 模块依赖关系摘要
    ├── class_index.md      # 类索引（按模块分组）
    ├── call_chains.md      # 关键调用链（router → service → client）
    └── api_surface.md      # API 接口面（router + schema）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GRAPH_DIR = PROJECT_ROOT / ".kimi" / "code-graph"
CONTEXT_DIR = PROJECT_ROOT / ".kimi" / "code-context"


def run_pyreverse() -> None:
    """运行 pyreverse 生成最新的 plantuml 文件。"""
    print("🔄 运行 pyreverse 分析代码...")
    pyreverse_path = Path(sys.executable).parent / "pyreverse"
    cmd = [
        str(pyreverse_path),
        "app/",
        "-o", "plantuml",
        "-p", "tez-operator",
        "--ignore", "tests,data,alembic,web",
    ]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode not in (0, 32):  # 32 = pyreverse 正常退出码
        print(f"⚠️ pyreverse 警告: {result.stderr}")

    # 移动生成的文件到 code-graph 目录
    for f in PROJECT_ROOT.glob("*.plantuml"):
        target = GRAPH_DIR / f.name
        f.rename(target)
        print(f"   📄 {target.name}")


def parse_packages_plantuml(path: Path) -> tuple[dict, list]:
    """解析 packages.plantuml，返回模块列表和依赖边。"""
    text = path.read_text(encoding="utf-8")
    modules: dict[str, str] = {}  # full_name -> short_name
    edges: list[tuple[str, str]] = []

    # 提取 package 定义
    for m in re.finditer(r'package "([^"]+)" as ([^\s{]+)', text):
        full_name, alias = m.groups()
        modules[alias] = full_name

    # 提取依赖边
    for m in re.finditer(r'(\S+)\s*-->\s*(\S+)', text):
        src, dst = m.groups()
        if src in modules and dst in modules:
            edges.append((modules[src], modules[dst]))

    return modules, edges


def parse_classes_plantuml(path: Path) -> dict:
    """解析 classes.plantuml，返回按模块分组的类信息。"""
    text = path.read_text(encoding="utf-8")
    classes: dict[str, dict] = {}

    # 匹配类定义块
    pattern = re.compile(
        r'class "([^"]+)" as ([^{\n]+)\s*\{([^}]*)\}',
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        class_name, full_path, body = m.groups()
        module = ".".join(full_path.split(".")[:-1])

        # 提取属性和方法
        attrs: list[str] = []
        methods: list[str] = []
        for line in body.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if "(" in line:
                methods.append(line)
            else:
                attrs.append(line)

        classes.setdefault(module, []).append({
            "name": class_name,
            "full_path": full_path,
            "attrs": attrs,
            "methods": methods,
        })

    return classes


def generate_module_deps(modules: dict, edges: list) -> str:
    """生成模块依赖关系 Markdown。"""
    lines = [
        "# 模块依赖关系\n",
        "> 自动生成，不要手动修改。运行 `python scripts/generate_code_context.py` 更新。\n",
    ]

    # 按层级分组
    layer_order = [
        ("入口层", ["app.main"]),
        ("路由层", [m for m in modules.values() if m.startswith("app.routers.")]),
        ("服务层", [m for m in modules.values() if m.startswith("app.services.")]),
        ("客户端层", [m for m in modules.values() if m.startswith("app.clients.")]),
        ("模型层", [m for m in modules.values() if m.startswith("app.models.")]),
        ("工具层", [m for m in modules.values() if m.startswith("app.utils.")]),
        ("其他", []),
    ]

    for layer_name, layer_modules in layer_order:
        lines.append(f"\n## {layer_name}\n")
        for mod in sorted(layer_modules):
            # 找到这个模块的出向依赖
            deps = sorted({dst for src, dst in edges if src == mod})
            if deps:
                lines.append(f"- **`{mod}`** → {', '.join(f'`{d}`' for d in deps)}")
            else:
                lines.append(f"- **`{mod}`**")

    return "\n".join(lines)


def generate_class_index(classes: dict) -> str:
    """生成类索引 Markdown。"""
    lines = [
        "# 类索引\n",
        "> 自动生成，不要手动修改。\n",
    ]

    priority_modules = [
        "app.routers",
        "app.services",
        "app.clients",
        "app.models",
        "app.schemas",
        "app.utils",
    ]

    # 优先模块放前面
    sorted_modules = sorted(
        classes.keys(),
        key=lambda m: (
            next((i for i, p in enumerate(priority_modules) if m.startswith(p)), 99),
            m,
        ),
    )

    for module in sorted_modules:
        lines.append(f"\n## `{module}`\n")
        for cls in classes[module]:
            lines.append(f"\n### `{cls['name']}`\n")
            if cls["attrs"]:
                lines.append("**属性:**")
                for attr in cls["attrs"]:
                    lines.append(f"- `{attr}`")
            if cls["methods"]:
                lines.append("**方法:**")
                for method in cls["methods"]:
                    lines.append(f"- `{method}`")

    return "\n".join(lines)


def generate_call_chains(edges: list) -> str:
    """提取关键调用链：router → service → client。"""
    lines = [
        "# 关键调用链\n",
        "> 从模块依赖推导出的核心数据流。\n",
    ]

    routers = sorted({src for src, _ in edges if src.startswith("app.routers.")})

    for router in routers:
        lines.append(f"\n## `{router}`\n")

        # 直接依赖的服务
        services = sorted({
            dst for src, dst in edges
            if src == router and dst.startswith("app.services.")
        })
        for svc in services:
            lines.append(f"\n### → `{svc}`\n")
            # 服务依赖的客户端
            clients = sorted({
                dst for src, dst in edges
                if src == svc and dst.startswith("app.clients.")
            })
            for cl in clients:
                lines.append(f"- → `{cl}`")
            # 服务依赖的模型
            models = sorted({
                dst for src, dst in edges
                if src == svc and dst.startswith("app.models.")
            })
            for mdl in models:
                lines.append(f"- → `{mdl}`")
            # 服务依赖的其他服务
            other_svcs = sorted({
                dst for src, dst in edges
                if src == svc and dst.startswith("app.services.") and dst != svc
            })
            for osvc in other_svcs:
                lines.append(f"- → `{osvc}` (同级服务)")

    return "\n".join(lines)


def generate_api_surface(classes: dict) -> str:
    """生成 API 接口面摘要：router + request/response schema。"""
    lines = [
        "# API 接口面\n",
        "> 自动从 routers 和 schemas 提取，用于快速了解系统能力。\n",
    ]

    # 收集 router 模块的类
    router_modules = {m: cls_list for m, cls_list in classes.items() if m.startswith("app.routers.")}
    schema_modules = {m: cls_list for m, cls_list in classes.items() if m.startswith("app.schemas.")}

    for mod, cls_list in sorted(router_modules.items()):
        router_name = mod.split(".")[-1]
        lines.append(f"\n## `{router_name}`\n")

        for cls in cls_list:
            if "Request" in cls["name"] or "Create" in cls["name"] or "Update" in cls["name"]:
                lines.append(f"\n**请求体:** `{cls['name']}`")
                for attr in cls.get("attrs", []):
                    lines.append(f"- `{attr}`")
            elif "Response" in cls["name"]:
                lines.append(f"\n**响应体:** `{cls['name']}`")
                for attr in cls.get("attrs", []):
                    lines.append(f"- `{attr}`")

    # 公共 Schema
    lines.append("\n---\n\n## 公共 Schema\n")
    for mod, cls_list in sorted(schema_modules.items()):
        for cls in cls_list:
            lines.append(f"\n### `{cls['name']}`")
            for attr in cls.get("attrs", []):
                lines.append(f"- `{attr}`")

    return "\n".join(lines)


def main() -> int:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 运行 pyreverse
    run_pyreverse()

    pkg_file = GRAPH_DIR / "packages_tez-operator.plantuml"
    cls_file = GRAPH_DIR / "classes_tez-operator.plantuml"

    if not pkg_file.exists() or not cls_file.exists():
        print("❌ pyreverse 未生成预期文件")
        return 1

    # 2. 解析
    print("\n📊 解析 PlantUML...")
    modules, edges = parse_packages_plantuml(pkg_file)
    classes = parse_classes_plantuml(cls_file)

    # 3. 生成上下文文件
    files = {
        "module_deps.md": generate_module_deps(modules, edges),
        "class_index.md": generate_class_index(classes),
        "call_chains.md": generate_call_chains(edges),
        "api_surface.md": generate_api_surface(classes),
    }

    print("\n📝 生成代码上下文文件:")
    for name, content in files.items():
        path = CONTEXT_DIR / name
        path.write_text(content, encoding="utf-8")
        lines = content.count("\n")
        print(f"   ✅ {name} ({lines} 行)")

    print(f"\n🎉 完成！上下文文件在: {CONTEXT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
