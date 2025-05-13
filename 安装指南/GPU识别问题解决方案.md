# GPU识别问题解决方案

## 问题描述

重装Python环境后，软件无法正确识别NVIDIA GPU，导致无法使用硬件加速功能。这通常表现为以下情况之一：

1. 软件提示"未检测到可用的GPU"，但同时显示"已启用GPU硬件加速"
2. 渲染或处理视频时速度明显变慢，CPU占用率高但GPU占用率低
3. 软件崩溃并显示与CUDA或GPU相关的错误信息

## 原因分析

重装Python后GPU识别失败的常见原因包括：

1. **依赖库路径问题**：新安装的Python环境中缺少必要的GPU相关依赖库
2. **版本不兼容**：Python版本与预编译的CUDA库不兼容（特别是Python 3.11+）
3. **环境变量丢失**：系统环境变量中CUDA路径配置丢失
4. **驱动版本冲突**：NVIDIA驱动版本与CUDA版本不匹配
5. **PyTorch/CUDA问题**：PyTorch与CUDA版本不匹配

## 解决方案

### 方案一：使用自动修复工具（推荐）

软件附带了自动修复工具，可以一键解决大多数GPU识别问题：

1. 进入`GPU工具`文件夹
2. 双击运行`一键修复GPU检测.bat`
3. 按照提示完成修复过程
4. 重启软件

### 方案二：手动修复步骤

如果自动修复工具无法解决问题，请按以下步骤手动修复：

#### 1. 检查NVIDIA驱动

确认NVIDIA驱动是否正常工作：

```
# 在命令提示符中运行
nvidia-smi
```

如果显示错误或未显示GPU信息，请重新安装最新版NVIDIA驱动。

#### 2. 重新安装GPU依赖

```
# 使用pip安装必要的GPU依赖
pip install numpy==1.24.3
pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 --index-url https://download.pytorch.org/whl/cu118
pip install GPUtil==1.4.0
pip install psutil==5.9.5
pip install pynvml>=11.5.0
```

#### 3. 强制启用NVIDIA GPU配置

在`GPU工具`文件夹中运行`启用NVIDIA加速.py`脚本，这将强制软件使用NVIDIA GPU。

#### 4. 修复NVIDIA服务

以管理员身份运行`修复NVIDIA显卡检测.bat`脚本，这将重启NVIDIA驱动服务。

### 方案三：完全重装CUDA环境

如果上述方法都无法解决问题，请尝试完全重装CUDA环境：

1. 卸载当前的CUDA和cuDNN
2. 下载并安装CUDA 11.8（与软件兼容的版本）
3. 下载并安装对应版本的cuDNN
4. 设置正确的环境变量：
   ```
   CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8
   Path=%Path%;%CUDA_PATH%\bin
   ```
5. 重新安装PyTorch（CUDA版本）：
   ```
   pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 --index-url https://download.pytorch.org/whl/cu118
   ```

## 安装GPU加速的最佳实践

为避免今后再次出现GPU识别问题，请遵循以下最佳实践：

1. **使用兼容的Python版本**：坚持使用Python 3.10.x，避免使用3.11+版本
2. **创建独立的虚拟环境**：为软件创建专用的虚拟环境，避免全局环境冲突
3. **按顺序安装依赖**：先安装CUDA，再安装PyTorch，最后安装其他依赖
4. **定期更新NVIDIA驱动**：保持显卡驱动为最新版本，但避免更新CUDA版本
5. **备份可用配置**：成功配置后，备份`%USERPROFILE%\VideoMixTool\gpu_config.json`文件

## 验证GPU是否正常工作

安装完成后，可以通过以下测试验证GPU是否正常工作：

1. 在软件中查看"关于"窗口，确认"GPU加速"状态为"已启用"
2. 运行以下Python代码检查PyTorch是否能识别GPU：

```python
import torch
print(f"CUDA可用: {torch.cuda.is_available()}")
print(f"GPU数量: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")
```

## 常见错误及解决方法

### 1. "CUDA error: no kernel image is available for execution on the device"

解决方法：确保安装了与显卡兼容的CUDA版本，对于较新的显卡，需要更新CUDA版本。

### 2. "ImportError: DLL load failed while importing _nvml"

解决方法：重新安装NVIDIA驱动，确保环境变量正确设置。

### 3. "CUDA initialization: CUDA driver version is insufficient for CUDA runtime version"

解决方法：更新NVIDIA驱动到最新版本，或降级CUDA版本以匹配当前驱动。

### 4. PyTorch报告CUDA可用，但软件仍无法识别GPU

解决方法：在`GPU工具`文件夹中运行`启用NVIDIA加速.py`强制启用GPU配置。 