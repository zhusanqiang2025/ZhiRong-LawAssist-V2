# rebuild-frontend.ps1
# PowerShell脚本 - 重新构建前端Docker镜像

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  前端Docker镜像自动重新构建脚本" -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# 获取当前时间戳作为构建版本
$buildVersion = Get-Date -Format "yyyyMMddHHmmss"
Write-Host "构建版本: $buildVersion" -ForegroundColor Green
Write-Host ""

try {
    # 1. 停止前端容器
    Write-Host "[1/6] 停止前端容器..." -ForegroundColor Yellow
    docker-compose stop frontend 2>$null
    Write-Host "    ✓ 容器已停止" -ForegroundColor Green

    # 2. 删除前端容器
    Write-Host "[2/6] 删除前端容器..." -ForegroundColor Yellow
    docker-compose rm -f frontend 2>$null
    Write-Host "    ✓ 容器已删除" -ForegroundColor Green

    # 3. 删除前端镜像
    Write-Host "[3/6] 删除前端镜像..." -ForegroundColor Yellow
    docker rmi legal_document_assistantv3-frontend 2>$null
    Write-Host "    ✓ 镜像已删除" -ForegroundColor Green

    # 4. 清理Docker构建缓存
    Write-Host "[4/6] 清理Docker构建缓存..." -ForegroundColor Yellow
    docker builder prune -f 2>$null | Out-Null
    Write-Host "    ✓ 缓存已清理" -ForegroundColor Green

    # 5. 重新构建前端镜像
    Write-Host "[5/6] 重新构建前端镜像..." -ForegroundColor Yellow
    Write-Host "    这可能需要几分钟..." -ForegroundColor Gray
    docker-compose build `
        --no-cache `
        --build-arg BUILD_VERSION=$buildVersion `
        frontend 2>&1 | Select-String -Pattern "(Step|built|Error|successfully)" | ForEach-Object {
            if ($_ -match "Step") { Write-Host "    $_" -ForegroundColor Gray }
            elseif ($_ -match "built successfully") { Write-Host "    ✓ 构建成功" -ForegroundColor Green }
            elseif ($_ -match "Error") { Write-Host "    ✗ 错误: $_" -ForegroundColor Red }
        }
    Write-Host "    ✓ 镜像构建完成" -ForegroundColor Green

    # 6. 启动前端容器
    Write-Host "[6/6] 启动前端容器..." -ForegroundColor Yellow
    docker-compose up -d frontend 2>&1 | Out-Null

    # 等待容器启动
    Start-Sleep -Seconds 3

    # 验证容器状态
    $containerStatus = docker ps --filter "name=frontend" --format "{{.Status}}"
    if ($containerStatus -match "Up") {
        Write-Host "    ✓ 容器已启动" -ForegroundColor Green

        # 显示容器中的JS文件
        Write-Host ""
        Write-Host "验证容器中的文件:" -ForegroundColor Cyan
        docker exec legal_assistant_v3_frontend sh -c "ls -lh /usr/share/nginx/html/assets/index-*.js" | ForEach-Object {
            Write-Host "    $_" -ForegroundColor Gray
        }
    } else {
        Write-Host "    ✗ 容器启动失败" -ForegroundColor Red
        Write-Host "    状态: $containerStatus" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================"  -ForegroundColor Cyan
    Write-Host "  重建完成！" -ForegroundColor Green
    Write-Host "========================================"  -ForegroundColor Cyan
    Write-Host ""
    Write-Host "请执行以下操作查看更新:" -ForegroundColor Yellow
    Write-Host "  1. 在浏览器中按 Ctrl+Shift+R 强制刷新" -ForegroundColor White
    Write-Host "  2. 或清除浏览器缓存后刷新" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "========================================"  -ForegroundColor Red
    Write-Host "  错误: $_" -ForegroundColor Red
    Write-Host "========================================"  -ForegroundColor Red
    Write-Host ""
    exit 1
}
