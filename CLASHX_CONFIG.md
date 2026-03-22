# ClashX 配置说明

## 问题描述

akshare需要访问东方财富网（eastmoney.com）的API来获取A股数据，但ClashX代理可能会阻止或错误路由这些请求。

## 解决方案1：在ClashX中添加直连规则（推荐）

在ClashX的配置文件中添加以下规则，让东方财富网的域名直连：

```yaml
rules:
  # 东方财富网直连（用于akshare获取A股数据）
  - DOMAIN-SUFFIX,eastmoney.com,DIRECT
  - DOMAIN-SUFFIX,eastmoney.net,DIRECT
  - DOMAIN,push2.eastmoney.com,DIRECT
  - DOMAIN,push2his.eastmoney.com,DIRECT
  - DOMAIN,quote.eastmoney.com,DIRECT

  # 其他规则...
```

### 如何修改ClashX配置：

1. 打开ClashX
2. 点击菜单栏的ClashX图标
3. 选择"配置" -> "打开配置文件夹"
4. 编辑你当前使用的配置文件（通常是.yaml文件）
5. 在`rules:`部分的**最前面**添加上述规则
6. 保存文件
7. 在ClashX中选择"配置" -> "重载配置文件"

## 解决方案2：代码中强制绕过代理

如果不想修改ClashX配置，代码已经自动处理了代理绕过。

## 验证

配置完成后，运行测试脚本验证：

```bash
python test_akshare_no_proxy.py
```

如果成功，你应该看到类似输出：

```
✓ 成功! 获取到 X 条数据
```
