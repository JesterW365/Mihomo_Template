# Mihomo Template Builder

这个项目只负责生成 Mihomo 配置模板，不负责抓取、转换或合并上游规则集。

## 目录结构

| 路径 | 用途 |
|---|---|
| `components/` | 可组合的配置片段，按 `head`、`dns`、`sniffer`、`strategy`、`rules` 分类 |
| `profiles/` | 模板生成方案，声明组件组合和输出文件名 |
| `providers.yaml` | 静态 `rule-providers` 数据库 |
| `scripts/merge.py` | 根据 profile 合并模板并自动注入实际引用的 providers |
| `Custom_templates/` | 生成后的 Mihomo 模板输出目录 |
| `tests/` | 单元测试 |

## 使用

安装依赖：

```bash
pip install -r requirements.txt
```

生成短模板：

```bash
python scripts/merge.py --profile short
```

生成 premrs 模板：

```bash
python scripts/merge.py --profile premrs
```

生成文件会输出到 `Custom_templates/`。

## Profile 格式

```yaml
name: short
output: short_template.yaml
components:
  head: head/premrs.yaml
  dns: dns/short.yaml
  sniffer: sniffer/premrs.yaml
  strategy: strategy/short.yaml
  rules: rules/short.yaml
```

`components` 中的路径相对于 `components/` 目录。`strategy` 和 `rules` 是必填组件。

## Provider 注入规则

`scripts/merge.py` 会扫描所有组件中的规则源引用：

- `RULE-SET,name,...`
- `rule-set:name`

然后只从 `providers.yaml` 输出实际被引用的 provider。引用了不存在的 provider 时，脚本会直接报错。
