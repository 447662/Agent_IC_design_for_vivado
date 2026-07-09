---
title: "Vivado 仿真器中的通用验证方法学 (Universal Verification Methodology, UVM) 支持"
source: "https://zhuanlan.zhihu.com/p/392964393"
author:
  - "[[芯语芯愿]]"
published:
created: 2026-07-09
description: "注：本文转自赛灵思中文社区论坛，源文链接 在此。本文原作者为XILINX工程师。以下为个人译文，仅供参考，如有疏漏之处，还请不吝赐教。 Vivado 集成设计环境支持将通用验证方法学 (UVM) 应用于 Vivado 仿真器。 V…"
tags:
  - "clippings"
---
3 人赞同了该文章

注：本文转自赛灵思中文社区论坛，源文链接 [在此](https://link.zhihu.com/?target=https%3A//forums.xilinx.com/t5/Design-and-Debug-Techniques-Blog/UVM-Universal-Verification-Methodology-Support-in-Vivado/ba-p/1070861) 。本文原作者为XILINX工程师。

以下为个人译文，仅供参考，如有疏漏之处，还请不吝赐教。

Vivado 集成设计环境支持将通用验证方法学 (UVM) 应用于 Vivado 仿真器。

Vivado 提供了预编译的 UVM V1.2 库。

请遵循以下步骤创建设计示例测试案例，以便在工程模式下使用 UVM。

（本文随附了 1 个简单示例，可供您下载解压使用）。

1. 在 Vivado 2019.2 中创建新 [RTL 工程](https://zhida.zhihu.com/search?content_id=175455579&content_type=Article&match_order=1&q=RTL+%E5%B7%A5%E7%A8%8B&zhida_source=entity) 。
2. 单击“添加目录 (Add Directories)”以将“src”和“verif”目录添加至该工程中。  
	指定 UVM 验证文件仅用于仿真 (Simulation Only)。
![](https://pic3.zhimg.com/v2-334385617305e6c09a984f8cfed520f4_1440w.jpg)

1. 选择工程所需的器件/开发板，然后单击“Next”。
2. 检查“工程摘要 (Project Summary)”，然后单击“完成 (Finish)”。
![](https://pic1.zhimg.com/v2-7e6146551873b45d8d4222b7c79458b8_1440w.jpg)

- 使用来自“src”和“verif”目录的新增源代码创建工程后，请转至“设置 (Settings)”->“仿真 (Simulation)”。  
	将“-L UVM”开关添加到位于“编译 (compilation)”选项卡下的 *[xsim.compile.xvlog.more\_options](https://zhida.zhihu.com/search?content_id=175455579&content_type=Article&match_order=1&q=xsim.compile.xvlog.more_options&zhida_source=entity)* 以及位于“细化 (Elaboration)”选项卡下的 *xsim.elaborate.xelab\_more\_options* （请参阅以下截屏）。  
	此开关是使用预编译的 UVM 库所必需的。
![](https://picx.zhimg.com/v2-db955762579df34f3666906e4b9c7aff_1440w.jpg)

![](https://pica.zhimg.com/v2-c8b434d7bbcb38a687110174cde53f56_1440w.jpg)

此外，还可通过 [Tcl 控制台](https://zhida.zhihu.com/search?content_id=175455579&content_type=Article&match_order=1&q=Tcl+%E6%8E%A7%E5%88%B6%E5%8F%B0&zhida_source=entity) (Tcl Console) 设置下列属性：

```
set_property -name {xsim.compile.xvlog.more_options} -value {-L uvm} -objects [get_filesets sim_1]
set_property -name {xsim.elaborate.xelab.more_options} -value {-L uvm} -objects [get_filesets sim_1]
```

如需了解这些步骤的相关信息，请参阅 [(UG900)](https://link.zhihu.com/?target=https%3A//china.xilinx.com/content/dam/xilinx/support/documentation/sw_manuals/xilinx2019_2/ug900-vivado-logic-simulation.pdf) 附录 C。

- 添加以上开关后，请确保已选中“adder\_4\_bit\_tb\_top.sv”文件作为顶层模块，然后运行仿真。  
	  
	仿真应可正常完成运行，但 Vivado 的“层级 (Hierarchy)”视图中的“源代码 (Sources)”窗口将显示这些文件上的语法错误。

您可忽略“Hierarchy”视图和 Vivado Text Editor 中的有关 UVM 的语法错误，因为 UVM 支持是在 Vivado 2019.2 中专为仿真器新增的。

对应 HSV 的 UVM 支持将于后续版本中提供。  

![](https://pic1.zhimg.com/v2-79858cad02e62b58407b26303eb237a2_1440w.jpg)

以下是非工程/批量模式下的 UVM 使用步骤：

- 调用 Vivado 2019.2：
```
source <Vivado_install_path>/Xilinx/Vivado/2019.2/settings64.sh
```
- 要以非工程模式运行仿真，请从当前工作目录切换至“run”文件夹。
```
cd ./Adder_4_bit/run
```
- 要在 Vivado 中运行独立仿真，可运行 run\_xsim.csh（在 Linux 上）和 run\_xsim.bat（在 Windows 上），或者也可在 Linux/Windows 中使用以下命令来运行 run.tcl。
```
Vivado –mode batch –source run.tcl
```
- 完成仿真后，可以在 shell 中或命令提示符中查看 UVM 测试结果，如下所示：
![](https://pic4.zhimg.com/v2-0945736fc1999ed6ae07065736432b3b_1440w.jpg)

![](https://pic4.zhimg.com/v2-5a2db0cda6ba39140a3959bdd82551f1_1440w.jpg)

**工程模式和非工程模式的目录结构：**

“src”和“verif”文件夹包含设计和验证环境相关的文件。

在非工程模式下，“Run”文件夹是运行仿真的位置。

UVM\_test 则用于在 [XSIM](https://zhida.zhihu.com/search?content_id=175455579&content_type=Article&match_order=1&q=XSIM&zhida_source=entity) 中以“工程模式”运行仿真。

发布于 2021-07-25 14:25[现场可编辑逻辑门阵列（FPGA）](https://www.zhihu.com/topic/19570427)

赞同 3