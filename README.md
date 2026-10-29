# scoop-lang.org

Scoop 编程语言的官方网站源码。纯静态站点，不依赖任何前端框架或 npm 包。

## 目录

- `src/layout.html` — 所有页面共用的外框（导航、页脚）。
- `src/pages/` — 页面正文片段。首行是元数据注释，例如
  `<!-- title: 语言导览; nav: tour; layout: docs; description: … -->`；
  `layout: docs` 会加上自动生成的侧边目录。
- `guides/` — 从 Scoop 仓库迁入的用户指南与文档大纲，使用带 YAML front matter 的 Jekyll Markdown。
  `guides/_layouts/guide.html` 提供页面布局与指南导航；`guides/examples/` 保存指南示例。
- `_config.yml`、`Gemfile`、`Gemfile.lock` — Jekyll 配置与固定的 Ruby 依赖；指南输出到 `dist/guides/`。
- `examples/` — 页面中嵌入的示例程序（唯一来源），`NAME.out` 是记录的运行输出。
  在页面中用 `{{example NAME}}` 嵌入代码和输出，`{{example NAME nooutput}}` 只嵌入代码。
- `assets/` — 样式、Scoop 语法高亮与页面脚本、logo。
- `tools/build.py` — 生成官网页面并调用 Jekyll，统一输出到 `dist/`。
- `tools/check_examples.py` — 用 `scoop` 编译运行官网和指南示例，并与 `.out` 比对。

## 构建

需要 Python 3、Ruby 和 Bundler。本地使用 Ruby 4.0 与 Jekyll 4.4 验证；macOS 自带的旧 Ruby 不适用，可以通过 Homebrew 安装：

```sh
brew install ruby
export PATH="$(brew --prefix ruby)/bin:$PATH"
```

在本站目录安装依赖：

```sh
bundle config set --local path vendor/bundle
bundle install
```

构建完整站点并预览：

```sh
python3 tools/build.py            # 生成 dist/，并把 ~/.scoop/docs/<target> 的 API 文档复制到 dist/api
python3 tools/build.py --no-api   # 跳过 API 文档
python3 tools/build.py --api-docs /path/to/scoop-doc-output
python3 -m http.server -d dist 8000
```

API 文档由 `scoop doc` 生成，随工具链安装在 `~/.scoop/docs/<target-triple>`。

指南入口为 `http://localhost:8000/guides/index.html`。单独修改指南时，可以在完成一次完整构建后运行 `bundle exec jekyll build`，或用 `bundle exec jekyll build --watch` 持续更新 `dist/guides/`；保留上述 HTTP 服务即可预览。Jekyll 单独构建只输出指南，官网页面、共享 assets 和 API 仍由 `tools/build.py` 准备。

## 编写指南

在 `guides/` 下新建 Markdown 文件，正文前写 YAML front matter：

```yaml
---
title: 指南标题
description: 一句话说明本文能帮助读者完成什么。
permalink: /topic.html
order: 30
---
```

`layout: guide` 由配置默认提供。`order` 控制侧边导航顺序；需要简短的导航名称时，增加 `nav_title`。所有指南页面使用平级 `/guides/*.html` 地址，`permalink` 不要再次加 `/guides`。

正文使用普通 Markdown，保留自己的一级标题。链接其他指南时使用 `{{ '/topic.html' | relative_url }}`，生成的链接会带上配置中的 `/guides` 前缀；链接编译器文档时使用 Scoop 仓库的 GitHub 地址。计划中的文章只记录在 `guides/OUTLINE.md`，完成后再添加页面与目录入口。

完整示例放在 `guides/examples/`，在代码围栏内用 `{% include_relative examples/NAME.scoop %}` 引用同一份源码，避免网页和可下载示例不一致。需要运行比对的示例增加 `.out`，所需参数在 `tools/check_examples.py` 的 `ARGS` 中配置。

## 验证示例

修改示例或升级工具链后：

```sh
export PATH="$HOME/.scoop/bin:$PATH"
python3 tools/check_examples.py            # 全部示例
python3 tools/check_examples.py json math  # 指定示例
python3 tools/check_examples.py word-stats # 指南中的文本统计程序
python3 tools/check_examples.py --update   # 用实际输出重写 .out
```

没有 `.out` 的示例（如会一直运行的 HTTP 服务）只检查能否编译。

更新技术说明时，以 Scoop 仓库当前 `docs/specs/`、CLI 定义和内置库源码为依据，区分已实现能力与后续设计；历史里程碑中的后端名称和旧工具包说明可能已经过时。修改共享示例后重新验证，构建时嵌入源码与实际预期输出。API 页面由 `scoop doc` 生成，应从匹配工具链的文档目录复制，不直接修改 `dist/api/`。

## 部署

`dist/` 是自包含的静态文件，可以直接发布到 GitHub Pages、Netlify、Cloudflare Pages 或任何静态文件服务器。

部署时先执行 `python3 tools/build.py`，再上传完整的 `dist/`。GitHub Pages 等平台应发布构建产物，不要只用默认 Jekyll 流程构建仓库根目录，否则会缺少既有官网页面与 API 文档。
