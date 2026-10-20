# web端对外展示页面

web技术栈选择：

- 想要做快速原型开发：`streamlit, nicegui`这些第三方模块，他们允许你使用python来写前端页面

- 想要做的精美细致：前端使用`Vue/React`。后端可以使用python的后端：Django, Flask, fastapi

  可以先用起来，然后再慢慢优化，慢慢学习

- 也可以使用其他的技术栈：前端+后端可以自由决策

我们做的分析做的可视化：这个技术栈固定：

- pandas+matplotlib+(pyecharts/plotly) 
- 如果你分析的数据量非常大：**Polars**一定程度允许使用这个
- 数据库、数据格式不做限制：sqllite，鼓励使用别的数据库：mysql,duckdb或者其他的
- 数据格式：不一定非得是数据库文件，可以使用任何格式的数据，csv. xlsx, 等等都可以