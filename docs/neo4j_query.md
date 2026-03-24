# Neo4j 查询指令集

适用数据库：`culturegraph`

## 0. 先看这一条

- 现在节点已经移除了通用标签 `:Entity`
- 所以不要再写 `MATCH (n:Entity)`
- 现在应优先使用：
  - 具体标签：`人物`、`地名`、`建筑遗迹`、`典籍作品`、`非遗技艺`、`朝代年号`、`历史事件`、`物产饮食`、`宗族姓氏`、`其他`
  - 或属性判断：`n.type = '人物'`

## 1. 图 / 表 / 统计图 的使用规则

### 1.1 图查询
用于 Neo4j 图视图。

要求：`RETURN 节点, 关系, 节点`

示例：

```cypher
MATCH (a:人物)-[r:REL]-(b)
RETURN a, r, b
LIMIT 200
```

### 1.2 表查询
用于看详细属性。

要求：`RETURN` 标量字段，不直接返回整节点。

示例：

```cypher
MATCH (a:人物)-[r:REL]-(b)
RETURN
  a.name AS 人物,
  r.rel_type AS 关系,
  b.name AS 关联对象,
  b.type AS 对象类型
LIMIT 200
```

### 1.3 统计图
用于柱状图 / 饼图 / 表格。

要求：返回“类别 + 数量”这类聚合结果。

示例：

```cypher
MATCH (n)
RETURN n.type AS 类型, count(*) AS 数量
ORDER BY 数量 DESC
```

运行后可在 Neo4j Browser 中切换到 `Table` / `Bar Chart` / `Pie Chart`。

---

## 2. 基础检查

### 2.1 查看所有标签

```cypher
CALL db.labels()
```

### 2.2 查看所有关系类型

```cypher
MATCH ()-[r]->()
RETURN type(r) AS Neo4j关系类型, count(*) AS 数量
ORDER BY 数量 DESC
```

### 2.3 查看实体类型分布（统计图/表）

```cypher
MATCH (n)
RETURN n.type AS 实体类型, count(*) AS 数量
ORDER BY 数量 DESC
```

### 2.4 查看业务关系分布（统计图/表）

```cypher
MATCH ()-[r:REL]->()
RETURN r.rel_type AS 关系类型, count(*) AS 数量
ORDER BY 数量 DESC
```

---

## 3. 人物查询

### 3.1 图：所有人物相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '人物' OR b.type = '人物'
RETURN a, r, b
LIMIT 500
```

### 3.2 图：人物 - 人物

```cypher
MATCH (a:人物)-[r:REL]-(b:人物)
RETURN a, r, b
LIMIT 300
```

### 3.3 表：人物关系明细（显示属性）

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '人物' OR b.type = '人物'
RETURN
  a.name AS 起点名称,
  a.type AS 起点类型,
  a.description AS 起点描述,
  a.confidence AS 起点置信度,
  a.mentions AS 起点提及次数,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件,
  b.name AS 终点名称,
  b.type AS 终点类型,
  b.description AS 终点描述,
  b.confidence AS 终点置信度,
  b.mentions AS 终点提及次数
LIMIT 500
```

### 3.4 统计图/表：人物最常见关系类型

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '人物' OR b.type = '人物'
RETURN r.rel_type AS 关系类型, count(*) AS 数量
ORDER BY 数量 DESC
LIMIT 30
```

---

## 4. 地名查询

> 注意：数据里使用的是 `地名`，不是 `地点`。

### 4.1 图：所有地名相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '地名' OR b.type = '地名'
RETURN a, r, b
LIMIT 500
```

### 4.2 图：地名 - 地名

```cypher
MATCH (a:地名)-[r:REL]-(b:地名)
RETURN a, r, b
LIMIT 300
```

### 4.3 表：地名关系明细

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '地名' OR b.type = '地名'
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  a.description AS 描述A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件,
  b.name AS 节点B,
  b.type AS 类型B,
  b.description AS 描述B
LIMIT 500
```

### 4.4 统计图/表：地名关联数量 Top 20

```cypher
MATCH (n:地名)-[r:REL]-()
RETURN n.name AS 地名, count(r) AS 关联数
ORDER BY 关联数 DESC
LIMIT 20
```

---

## 5. 建筑遗迹查询

> 注意：数据里使用的是 `建筑遗迹`，不是 `建筑`。

### 5.1 图：所有建筑遗迹相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '建筑遗迹' OR b.type = '建筑遗迹'
RETURN a, r, b
LIMIT 500
```

### 5.2 图：建筑遗迹 - 建筑遗迹

```cypher
MATCH (a:建筑遗迹)-[r:REL]-(b:建筑遗迹)
RETURN a, r, b
LIMIT 300
```

### 5.3 表：建筑遗迹关系明细

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '建筑遗迹' OR b.type = '建筑遗迹'
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  a.description AS 描述A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件,
  b.name AS 节点B,
  b.type AS 类型B,
  b.description AS 描述B
LIMIT 500
```

### 5.4 统计图/表：建筑遗迹关联数量 Top 20

```cypher
MATCH (n:建筑遗迹)-[r:REL]-()
RETURN n.name AS 建筑遗迹, count(r) AS 关联数
ORDER BY 关联数 DESC
LIMIT 20
```

---

## 6. 典籍作品查询

### 6.1 图：所有典籍作品相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '典籍作品' OR b.type = '典籍作品'
RETURN a, r, b
LIMIT 500
```

### 6.2 表：典籍作品关系明细

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '典籍作品' OR b.type = '典籍作品'
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  a.description AS 描述A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B,
  b.description AS 描述B
LIMIT 500
```

### 6.3 统计图/表：典籍作品关联数量 Top 20

```cypher
MATCH (n:典籍作品)-[r:REL]-()
RETURN n.name AS 典籍作品, count(r) AS 关联数
ORDER BY 关联数 DESC
LIMIT 20
```

---

## 7. 非遗技艺查询

### 7.1 图：所有非遗技艺相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '非遗技艺' OR b.type = '非遗技艺'
RETURN a, r, b
LIMIT 500
```

### 7.2 表：非遗技艺关系明细

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '非遗技艺' OR b.type = '非遗技艺'
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  a.description AS 描述A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B,
  b.description AS 描述B
LIMIT 500
```

### 7.3 统计图/表：非遗技艺关联数量 Top 20

```cypher
MATCH (n:非遗技艺)-[r:REL]-()
RETURN n.name AS 非遗技艺, count(r) AS 关联数
ORDER BY 关联数 DESC
LIMIT 20
```

---

## 8. 历史事件查询

### 8.1 图：所有历史事件相关关系

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '历史事件' OR b.type = '历史事件'
RETURN a, r, b
LIMIT 500
```

### 8.2 表：历史事件关系明细

```cypher
MATCH (a)-[r:REL]-(b)
WHERE a.type = '历史事件' OR b.type = '历史事件'
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  a.description AS 描述A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B,
  b.description AS 描述B
LIMIT 500
```

### 8.3 统计图/表：历史事件关联数量 Top 20

```cypher
MATCH (n:历史事件)-[r:REL]-()
RETURN n.name AS 历史事件, count(r) AS 关联数
ORDER BY 关联数 DESC
LIMIT 20
```

---

## 9. 组合关系查询

## 9.1 人物 × 地名

### 图

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '人物' AND b.type = '地名') OR
  (a.type = '地名' AND b.type = '人物')
RETURN a, r, b
LIMIT 300
```

### 表

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '人物' AND b.type = '地名') OR
  (a.type = '地名' AND b.type = '人物')
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B
LIMIT 300
```

## 9.2 人物 × 建筑遗迹

### 图

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '人物' AND b.type = '建筑遗迹') OR
  (a.type = '建筑遗迹' AND b.type = '人物')
RETURN a, r, b
LIMIT 300
```

### 表

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '人物' AND b.type = '建筑遗迹') OR
  (a.type = '建筑遗迹' AND b.type = '人物')
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B
LIMIT 300
```

## 9.3 建筑遗迹 × 地名

### 图

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '建筑遗迹' AND b.type = '地名') OR
  (a.type = '地名' AND b.type = '建筑遗迹')
RETURN a, r, b
LIMIT 300
```

### 表

```cypher
MATCH (a)-[r:REL]-(b)
WHERE
  (a.type = '建筑遗迹' AND b.type = '地名') OR
  (a.type = '地名' AND b.type = '建筑遗迹')
RETURN
  a.name AS 节点A,
  a.type AS 类型A,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  b.name AS 节点B,
  b.type AS 类型B
LIMIT 300
```

---

## 10. 指定名称模板

## 10.1 指定人物

### 图

```cypher
MATCH (p:人物)-[r:REL]-(x)
WHERE p.name = '康有为'
RETURN p, r, x
LIMIT 200
```

### 表

```cypher
MATCH (p:人物)-[r:REL]-(x)
WHERE p.name = '康有为'
RETURN
  p.name AS 人物,
  p.description AS 人物描述,
  x.name AS 关联对象,
  x.type AS 关联对象类型,
  x.description AS 关联对象描述,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件
LIMIT 200
```

## 10.2 指定地名

### 图

```cypher
MATCH (p:地名)-[r:REL]-(x)
WHERE p.name = '西樵山'
RETURN p, r, x
LIMIT 200
```

### 表

```cypher
MATCH (p:地名)-[r:REL]-(x)
WHERE p.name = '西樵山'
RETURN
  p.name AS 地名,
  p.description AS 地名描述,
  x.name AS 关联对象,
  x.type AS 关联对象类型,
  x.description AS 关联对象描述,
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件
LIMIT 200
```

## 10.3 模糊搜索名称

### 表

```cypher
MATCH (n)
WHERE n.name CONTAINS '西樵'
RETURN
  n.name AS 名称,
  n.type AS 类型,
  n.description AS 描述,
  n.mentions AS 提及次数,
  n.confidence AS 置信度
LIMIT 100
```

---

## 11. 常用速查

### 11.1 所有节点总数

```cypher
MATCH (n)
RETURN count(n) AS 节点总数
```

### 11.2 所有关系总数

```cypher
MATCH ()-[r:REL]->()
RETURN count(r) AS 关系总数
```

### 11.3 查看节点属性样本

```cypher
MATCH (n)
RETURN
  n.name AS 名称,
  n.type AS 类型,
  n.description AS 描述,
  n.confidence AS 置信度,
  n.mentions AS 提及次数,
  n.is_anchor AS 是否锚点,
  n.color AS 颜色
LIMIT 50
```

### 11.4 查看关系属性样本

```cypher
MATCH ()-[r:REL]->()
RETURN
  r.rel_type AS 关系类型,
  r.confidence AS 关系置信度,
  r.evidence AS 关系证据,
  r.source_file AS 来源文件
LIMIT 50
```

---

## 12. 推荐使用顺序

1. 先跑 `2.3` 看实体类型分布
2. 再跑你关心的类型，例如 `4`、`5`
3. 先看“图”，确认结构
4. 再看“表”，检查属性和证据
5. 最后看“统计图/表”，做数量分析
