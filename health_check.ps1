# 健康检查脚本 - 持续监控服务状态
# 使用方法: .\health_check.ps1

$SERVICE_URL = "http://localhost:9900"
$CHECK_INTERVAL = 60  # 检查间隔（秒）
$ALERT_THRESHOLD = 3  # 连续失败次数阈值

$failCount = 0

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  老年人Agent系统 - 健康检查监控" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "监控地址: $SERVICE_URL"
Write-Host "检查间隔: $CHECK_INTERVAL 秒"
Write-Host "告警阈值: 连续失败 $ALERT_THRESHOLD 次"
Write-Host "按 Ctrl+C 停止监控"
Write-Host "--------------------------------------`n"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    try {
        # 健康检查
        $response = Invoke-RestMethod -Uri "$SERVICE_URL/health" -TimeoutSec 10 -ErrorAction Stop

        if ($response.code -eq 200) {
            # 服务正常
            $failCount = 0
            Write-Host "[$timestamp] ✓ 服务正常运行" -ForegroundColor Green

            # 显示详细状态
            $milvusStatus = $response.data.milvus.status
            Write-Host "  └─ Milvus: $milvusStatus" -ForegroundColor Gray

        } else {
            # 服务异常
            $failCount++
            Write-Host "[$timestamp] ✗ 服务异常 (失败次数: $failCount)" -ForegroundColor Yellow
            Write-Host "  └─ 错误信息: $($response.message)" -ForegroundColor Yellow

            # 达到告警阈值
            if ($failCount -ge $ALERT_THRESHOLD) {
                Write-Host "`n!!! [告警] 服务连续 $failCount 次检查失败 !!!" -ForegroundColor Red -BackgroundColor White
                Write-Host "错误详情: $($response.data.error)" -ForegroundColor Red

                # TODO: 这里可以添加告警通知
                # 例如: 发送 Webhook 消息

                # 重置计数器（避免重复告警）
                $failCount = 0
            }
        }

    } catch {
        # 请求失败
        $failCount++
        Write-Host "[$timestamp] ✗ 无法连接到服务 (失败次数: $failCount)" -ForegroundColor Red
        Write-Host "  └─ 错误: $($_.Exception.Message)" -ForegroundColor Red

        # 达到告警阈值
        if ($failCount -ge $ALERT_THRESHOLD) {
            Write-Host "`n!!! [告警] 服务无响应，连续 $failCount 次检查失败 !!!" -ForegroundColor Red -BackgroundColor White
            Write-Host "请检查:" -ForegroundColor Yellow
            Write-Host "  1. 服务是否启动？运行: .\start-windows.bat" -ForegroundColor Yellow
            Write-Host "  2. 端口是否被占用？运行: netstat -ano | findstr :9900" -ForegroundColor Yellow
            Write-Host "  3. 查看日志: type logs\app_$(Get-Date -Format 'yyyy-MM-dd').log" -ForegroundColor Yellow

            # 重置计数器（避免重复告警）
            $failCount = 0
        }
    }

    # 等待下次检查
    Start-Sleep -Seconds $CHECK_INTERVAL
}
