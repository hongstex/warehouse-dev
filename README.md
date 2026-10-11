# warehouse-dev

5 楼面料仓（3#楼）货架规划：方案 A/B 对比、2D/3D 展示、仓位与用料估算。

## 目录
- `public/` — 静态展示站（Cloudflare Pages 发布目录）
  - `index.html` — 方案切换、2D 平面（可查仓位）、3D 立体（three.js，CDN 加载）、用料表（单价可改）
  - `data/layout_{A,B}.json` — 布置、仓位、货架段、用料数据（网页读取）
  - `files/layout_5F_{A,B}_v1.{png,pdf,dxf}` — 下载文件（DXF 可直接在 AutoCAD 打开，单位 mm）
- `layout/generate.py` — 参数化出图脚本，改参数后重新生成 `public/` 下的数据和文件
- `layout/optimize_rows.py` — 排位优化（柱网避让）
- `docs/方案说明_v1.md` — 方案说明全文

## 更新方案
```bash
pip install ezdxf matplotlib
python3 layout/generate.py     # 重新生成 public/data 和 public/files
git commit -am "..." && git push   # Cloudflare Pages 自动部署
```
生成物已提交到仓库，Cloudflare 端不需要 Python 环境。

## Cloudflare Pages 设置
Workers & Pages → Create → Pages → Connect to Git → 选择本仓库：
- Production branch：`main`（或当前开发分支）
- Framework preset：None
- Build command：留空
- Build output directory：`public`

其他分支推送后会自动生成预览地址（`<branch>.<project>.pages.dev`）。
站点默认公开且已设置 `noindex`；如需限制访问，在 Cloudflare Zero Trust → Access 中为该 Pages 域名加访问策略（如仅允许指定邮箱）。
