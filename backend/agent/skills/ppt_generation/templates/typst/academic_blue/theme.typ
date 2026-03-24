// Academic Blue 主题 — 16:9 学术演示文稿
// 配色方案

#let primary-color = rgb("#1a56db")
#let secondary-color = rgb("#3b82f6")
#let bg-color = rgb("#f8fafc")
#let text-color = rgb("#1e293b")

// 页面设置
#set page(
  width: 254mm,
  height: 142.9mm,
  margin: 1.5cm,
  fill: bg-color,
)

// 字体设置
#set text(
  size: 14pt,
  fill: text-color,
)

// slide 函数
#let slide(body) = {
  pagebreak(weak: true)
  body
}
