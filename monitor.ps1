# 系统监控脚本 - 显示实时状态和错误
# 使用方法: .\monitor.ps1

$SERVICE_URL = "http://localhost:9900"

function Show-Status {
    Clear-Host
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  老年人Agent系统 - 实时监控" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "更新时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"

    try {
        # 获取系统状态
        $status = Invoke-RestMethod -Uri "$SERVICE_URL/api/monitoring/status" -TimeoutSec 5

        if ($status.code -eq 200) {
            $data = $status.data

            Write-Host "【服务信息】" -ForegroundColor Green
            Write-Host "  服务名称: $($data.service.name)"
            Write-Host "  进程 PID: $($data.service.pid)"
            Write-Host "  运行时长: $([math]::Round($data.service.uptime_seconds / 60, 2)) 分钟"
            Write-Host "  状态: $($data.service.status)" -ForegroundColor Green

            Write-Host "`n【系统资源】" -ForegroundColor Cyan
            Write-Host "  CPU 使用率: $($data.system.cpu_percent)%"

            $memPercent = $data.system.memory.percent
            $memColor = if ($memPercent -gt 80) { "Red" } elseif ($memPercent -gt 60) { "Yellow" } else { "Green" }
            Write-Host "  内存使用: $($data.system.memory.used_gb) GB / $($data.system.memory.total_gb) GB ($memPercent%)" -ForegroundColor $memColor

            $diskPercent = $data.system.disk.percent
            $diskColor = if ($diskPercent -gt 80) { "Red" } elseif ($diskPercent -gt 60) { "Yellow" } else { "Green" }
            Write-Host "  磁盘使用: $($data.system.disk.used_gb) GB / $($data.system.disk.total_gb) GB ($diskPercent%)" -ForegroundColor $diskColor

            Write-Host "`n【进程资源】" -ForegroundColor Cyan
            Write-Host "  进程内存: $($data.process.memory_mb) MB"
            Write-Host "  线程数: $($data.process.threads)"

        } else {
            Write-Host "✗ 无法获取系统状态" -ForegroundColor Red
        }

    } catch {
        Write-Host "✗ 服务连接失败: $($_.Exception.Message)" -ForegroundColor Red
    }

    # 获取最近错误
    try {
        $errors = Invoke-RestMethod -Uri "$SERVICE_URL/api/monitoring/errors" -TimeoutSec 5

        Write-Host "`n【最近错误】($($errors.data.total) 条)" -ForegroundColor Yellow
        if ($errors.data.errors.Count -gt 0) {
            $errors.data.errors | Select-Object -Last 10 | ForEach-Object {
                Write-Host "  $_" -ForegroundColor Red
            }
        } else {
            Write-Host "  暂无错误日志" -ForegroundColor Green
        }

    } catch {
        Write-Host "`n✗ 无法获取错误日志" -ForegroundColor Red
    }

    Write-Host "`n--------------------------------------"
    Write-Host "按 Ctrl+C 退出监控，5秒后自动刷新..." -ForegroundColor Gray
}

# 主循环
while ($true) {
    Show-Status
    Start-Sleep -Seconds 5
}
