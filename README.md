# warehouse-dev

面料仓（3#楼标准层）货架规划。

- `docs/方案说明_v0.md` — 布置思路、指标、风险
- `output/layout_v0.png|pdf|dxf` — 布置草图（DXF 可直接在 AutoCAD 打开）
- `layout/generate.py` — 参数化出图脚本（`pip install ezdxf matplotlib && python3 layout/generate.py`）
- `layout/optimize_rows.py` — 排位优化（柱网避让）
