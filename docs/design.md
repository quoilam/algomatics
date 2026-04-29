--- 
# 设计文档
用于描述项目的早期设计想法, 不代表最终实现

---

我希望实现一个**多agent驱动**的图像算法自动化系统, 项目必须是Lagentic的, 不能是传统的pipeline或workflow这种固定的流程, 需要有动态的agent编排和调度能力, 以及状态展示能力

文中提到的agent指都是基于大模型的智能agent, 通过调用大模型的能力来实现特定的功能, 例如检索、代码生成、评估、执行等等, 而不是传统意义上的业务逻辑agent

agentic指的是系统具有动态的agent编排和调度能力, 可以根据不同的用户输入和场景需求, 动态地选择和组合不同的agent来完成任务, 而不是预先定义好固定的流程或pipeline, 这样可以更灵活地适应不同的需求和变化, 并且能够更好地利用不同agent的能力来完成复杂的任务

### 系统架构: 
- 一个controller控制器, 用于agent的编排和调度, 以及对用户输入的处理
- 多个agent, 每个agent负责一个特定的功能模块, 例如检索、代码生成、评估、执行等等, 这些agent可以独立开发和部署, 通过controller进行协调和通信
- 用户UI界面, 用户输入场景提示词(eg.把这张图卡通化)和示例图片, 调用controller完成任务, 最终将结果返回给用户界面展示

### controller设计
见 [controller设计](controller-impl.md)

### agent编排
见 [agent编排](agents-impl.md)

### 项目实现要求
见 [项目实现要求](project-impl.md)

### 业务流程要求
见 [业务流程要求](biz-impl.md)