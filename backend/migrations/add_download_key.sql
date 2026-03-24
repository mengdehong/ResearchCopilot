-- Publish WF 报告包下载路径
ALTER TABLE run_snapshots ADD COLUMN IF NOT EXISTS download_key TEXT;
