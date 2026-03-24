操作步骤：

1. 先停掉当前正在跑的进程（在你跑着的那个终端里按 Ctrl+C）

2. 打开两个终端，分别执行：

终端 A（跑前半部分的文件）：

python "C:\Users\ms\Desktop\graduation\毕设\中期阶段\code\data_processing\llm_ner.py" --worker 0/2
终端 B（跑后半部分的文件）：

python "C:\Users\ms\Desktop\graduation\毕设\中期阶段\code\data_processing\llm_ner.py" --worker 1/2
原理说明：

项目	Worker 0	Worker 1
分到的文件	未完成文件的前半	未完成文件的后半
进度文件	progress_w0.json	progress_w1.json
日志文件	extraction_log_w0.log	extraction_log_w1.log
实体/关系	写各自文件的 JSON（不冲突）	写各自文件的 JSON（不冲突）
已跑完的 9 篇（记在 progress.json 的 completed_files 里）会被两个 worker 都跳过
当前正在跑的 010_南海市文化艺术志（chunk 级断点在 entities JSON 里），分到哪个 worker 就由哪个 worker 从断点继续
两个都跑完后，执行 --merge-only 合并：
python "C:\Users\ms\Desktop\graduation\毕设\中期阶段\code\data_processing\llm_ner.py" --merge-only
