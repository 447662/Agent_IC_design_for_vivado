---
title: "在Vivado 仿真器中搭建UVM验证环境（不需要联合modelsim）"
source: "http://www.pswp.cn/news/202408.shtml?action=onClick"
author:
published:
created: 2026-07-09
description: "Vivado 集成设计环境支持将通用验证方法学 (UVM) 应用于 Vivado 仿真器。Vivado 提供了预编译的 UVM V1.2 库。 （1）在 Vivado 2019.2 中创建新 RTL 工程。 （2）单击“添加目录 (Add Directories)”以将“src”和“verif”目录添加…"
tags:
  - "clippings"
---
Vivado 集成设计环境支持将通用验证方法学 (UVM) 应用于 Vivado 仿真器。Vivado 提供了预编译的 UVM V1.2 库。

#### （1）在 Vivado 2019.2 中创建新 RTL 工程。

#### （2）单击“添加目录 (Add Directories)”以将“src”和“verif”目录添加至该工程中。 指定 UVM 验证文件仅用于仿真 (Simulation Only)。

![](https://img-blog.csdnimg.cn/direct/efe6608db02f4d138534c76aa7f299b4.png)

#### （3）选择工程所需的器件/开发板，然后单击“Next”。

#### （4）检查“工程摘要 (Project Summary)”，然后单击“完成 (Finish)”。

![](https://img-blog.csdnimg.cn/direct/a66533da20cc4ce18729c9bade9bfcab.png)

使用来自“src”和“verif”目录的新增源代码创建工程后，请转至“设置 (Settings)”->“仿真 (Simulation)”。  
将“-L UVM”开关添加到位于“编译 (compilation)”选项卡下的 *xsim.compile.xvlog.more\_options* 以及位于“细化 (Elaboration)”选项卡下的 *xsim.elaborate.xelab\_more\_options* （请参阅下图）。此开关是使用预编译的 UVM 库所必需的。  
![](https://img-blog.csdnimg.cn/direct/5ada534c84a74592a4085c72a1248fdd.png)  
![](https://img-blog.csdnimg.cn/direct/b893a3285c5a49ff8a4926f909b6f8e2.png)

此外，还可通过 Tcl 控制台 (Tcl Console) 设置下列属性：

```
set_property -name {xsim.compile.xvlog.more_options} -value {-L uvm} -objects [get_filesets sim_1]
set_property -name {xsim.elaborate.xelab.more_options} -value {-L uvm} -objects [get_filesets sim_1]
```

如需了解这些步骤的相关信息，请参阅 (UG900) 附录 C。

- 添加以上开关后，请确保已选中“adder\_4\_bit\_tb\_top.sv”文件作为顶层模块，然后运行仿真。  
	  
	仿真应可正常完成运行，但 Vivado 的“层级 (Hierarchy)”视图中的“源代码 (Sources)”窗口将显示这些文件上的语法错误。

您可忽略“Hierarchy”视图和 Vivado Text Editor 中的有关 UVM 的语法错误，因为 UVM 支持是在 Vivado 2019.2 中专为仿真器新增的。

#### （5）以下是非工程/批量模式下的 UVM 使用步骤：

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
	参考：  
	AMD Customer Community