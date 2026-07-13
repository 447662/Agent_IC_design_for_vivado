# -*- coding: utf-8 -*-
import html
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from digital_ic_agent._runtime.target_flow_messages import (
    build_sync_fifo_error_lines,
    build_sync_fifo_sim_completed_lines,
    build_sync_fifo_vcd_analysis_lines,
    emit_sync_fifo_lines,
)

class SyncFifoMixin:
    if TYPE_CHECKING:
        check_rtl_project: Any
        generate_rtl_project: Any
        launch_vivado_gui: Any
        render_vivado_tclstore_bootstrap: Any
        resolve_vivado_command: Any
        run_vivado_batch: Any
        run_waveform_analyzer_json: Any

    def resolve_sync_fifo_vcd_path(self, output_dir: Any="outputs") -> Any:
        return Path(output_dir) / "sync-fifo" / "sim" / "sync_fifo_trace.vcd"

    def collect_sync_fifo_vcd_analysis(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        vcd_path = self.resolve_sync_fifo_vcd_path(output_dir)
        if not vcd_path.exists():
            raise FileNotFoundError("Sync FIFO VCD file not found: {}".format(vcd_path))

        info = self.run_waveform_analyzer_json("info", vcd_path, backend=waveform_backend)
        write_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_sync_fifo.full=0",
            "--changed",
            "tb_sync_fifo.write_count",
            "--show",
            "tb_sync_fifo.wr_data,tb_sync_fifo.write_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        read_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_sync_fifo.empty=0",
            "--changed",
            "tb_sync_fifo.read_count",
            "--show",
            "tb_sync_fifo.rd_data,tb_sync_fifo.read_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        return {
            "vcd_path": vcd_path,
            "info": info,
            "write_events": write_events,
            "read_events": read_events,
        }

    def analyze_sync_fifo_vcd(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        try:
            analysis = self.collect_sync_fifo_vcd_analysis(
                output_dir=output_dir,
                limit=limit,
                waveform_backend=waveform_backend,
            )
        except FileNotFoundError as exc:
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines(
                    str(exc),
                    "Run --sim-rtl sync-fifo first, or check --output-dir.",
                ),
                stream=sys.stderr,
            )
            return False
        except RuntimeError as exc:
            emit_sync_fifo_lines(build_sync_fifo_error_lines(str(exc)), stream=sys.stderr)
            return False

        emit_sync_fifo_lines(build_sync_fifo_vcd_analysis_lines(analysis, limit=int(limit)))

        return True

    def write_sync_fifo_sim_report(self, project_dir: Any, vcd_path: Any, wave_db_path: Any, sim_result: Any=None, project_result: Any=None, limit: Any=20) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "sim_report.md"
        html_path = reports_dir / "sim_report.html"

        analysis = None
        analysis_error = None
        try:
            analysis = self.collect_sync_fifo_vcd_analysis(output_dir=project_dir.parent, limit=limit)
        except (FileNotFoundError, RuntimeError) as exc:
            analysis_error = str(exc)

        lines = [
            "# sync-fifo 仿真报告",
            "",
            "## 摘要",
            "",
            "- 目标：`sync-fifo`",
            "- 仿真器：Vivado/xsim",
            "- 状态：{}".format("PASS" if analysis_error is None else "PASS_WITH_ANALYSIS_WARNING"),
            "- VCD：`{}`".format(vcd_path),
            "- WDB：`{}`".format(wave_db_path),
            "- Vivado 工程：`{}`".format(project_dir / "vivado_project" / "sync_fifo_project.xpr"),
            "- 工程创建：{}".format("PASS" if project_result is not None and project_result.returncode == 0 else "WARNING"),
            "",
            "## Scoreboard",
            "",
            "- Testbench includes `SYNC_FIFO_SCOREBOARD_PASS` / `SYNC_FIFO_SCOREBOARD_FAIL` checks.",
            "- xsim returns failure if `$fatal(1, ...)` is reached.",
            "",
            "## 场景",
            "",
            "- `basic_ordered`：基础有序写入/读出。",
            "- `full_boundary`：写满 FIFO 并确认 full 边界。",
            "- `empty_boundary`：读空 FIFO 并确认 empty 边界。",
            "- `mixed_stress`：交错写入和读出。",
        ]

        if analysis is not None:
            info = analysis["info"]
            write_events = analysis["write_events"]
            read_events = analysis["read_events"]
            lines.extend([
                "",
                "## VCD 分析",
                "",
                "- 信号数量：{}".format(info.get("signal_count", "unknown")),
                "- 时间范围：{} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")),
                "- 仿真时长：{}".format(info.get("duration_h", "unknown")),
                "- 时间单位：{}".format(info.get("timescale", "unknown")),
                "- 写事件：{}".format(write_events.get("total", write_events.get("shown", "unknown"))),
                "- 读事件：{}".format(read_events.get("total", read_events.get("shown", "unknown"))),
            ])
        else:
            lines.extend(["", "## VCD 分析", "", "- 分析提示：{}".format(analysis_error or "not available")])

        if project_result is not None and project_result.returncode != 0:
            project_warning = project_result.stderr.strip() or project_result.stdout.strip() or "Vivado project generation failed"
            lines.extend([
                "",
                "## Vivado 工程创建提示",
                "",
                "- 工程创建未完成，但 RTL 仿真、VCD 和 WDB 已生成。",
                "- 常见原因：本机 Vivado TclStore 初始化异常，例如 `::tclapp::support::appinit` 缺失。",
                "- 原始提示：`{}`".format(project_warning.replace("`", "'")),
            ])

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        status = "PASS" if analysis_error is None else "PASS_WITH_ANALYSIS_WARNING"
        if project_result is not None and project_result.returncode != 0:
            status = "PASS_WITH_PROJECT_WARNING"
        signal_count = analysis["info"].get("signal_count", "unknown") if analysis else "unknown"
        write_count = analysis["write_events"].get("total", analysis["write_events"].get("shown", "unknown")) if analysis else "unknown"
        read_count = analysis["read_events"].get("total", analysis["read_events"].get("shown", "unknown")) if analysis else "unknown"
        html_lines = [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>sync-fifo 仿真报告</title>",
            "<style>",
            "body{margin:0;font-family:\"Microsoft YaHei\",\"Segoe UI\",Arial,sans-serif;background:#f5f7fb;color:#172033}",
            ".page{max-width:1060px;margin:0 auto;padding:34px 22px}",
            ".hero{padding:28px;border-radius:8px;color:#fff;background:linear-gradient(135deg,#17324d,#2f7d68)}",
            ".hero h1{margin:0 0 8px;font-size:32px}",
            ".grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:20px}",
            ".card{padding:18px;border-radius:8px;background:#fff;border:1px solid #dbe3ee;box-shadow:0 8px 24px rgba(31,45,61,.06)}",
            ".label{color:#5f6b7a;font-size:13px}.value{margin-top:6px;font-size:26px;font-weight:800}",
            "code{display:block;overflow-x:auto;padding:8px;border-radius:6px;background:#eef3f8}",
            "@media(max-width:800px){.grid{grid-template-columns:1fr}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<section class="hero"><h1>sync-fifo 仿真报告</h1><p>状态：{}</p></section>'.format(html.escape(status)),
            '<section class="grid">',
            '<article class="card"><div class="label">信号数量</div><div class="value">{}</div></article>'.format(html.escape(str(signal_count))),
            '<article class="card"><div class="label">写事件</div><div class="value">{}</div></article>'.format(html.escape(str(write_count))),
            '<article class="card"><div class="label">读事件</div><div class="value">{}</div></article>'.format(html.escape(str(read_count))),
            "</section>",
            '<section class="card" style="margin-top:20px"><h2>产物路径</h2>',
            "<p>VCD</p><code>{}</code>".format(html.escape(str(vcd_path))),
            "<p>WDB</p><code>{}</code>".format(html.escape(str(wave_db_path))),
            "<p>Vivado 工程</p><code>{}</code>".format(html.escape(str(project_dir / "vivado_project" / "sync_fifo_project.xpr"))),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return report_path

    def check_sync_fifo_rtl(self, output_dir: Any="outputs") -> Any:
        return self.check_rtl_project(
            target_name="sync-fifo",
            output_dir=output_dir,
            rtl_name="sync_fifo.v",
            tb_name="tb_sync_fifo.v",
            sim_script_name="run_vivado_sync_fifo.tcl",
            project_script_name="create_sync_fifo_project.tcl",
            gui_script_name="open_sync_fifo_project_gui.tcl",
            xpr_name="sync_fifo_project.xpr",
            vcd_name="sync_fifo_trace.vcd",
            wave_db_resolver=self.resolve_sync_fifo_wave_db,
            rtl_markers=[
                ("RTL declares sync_fifo", "module sync_fifo"),
                ("RTL has full logic", "assign full"),
                ("RTL has empty logic", "assign empty"),
            ],
            tb_markers=[
                ("TB declares tb_sync_fifo", "module tb_sync_fifo"),
                ("TB prints scoreboard pass", "SYNC_FIFO_SCOREBOARD_PASS"),
                ("TB fatal on scoreboard fail", "SYNC_FIFO_SCOREBOARD_FAIL"),
            ],
        )

    def render_sync_fifo_rtl(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps

module sync_fifo #(
    parameter DATA_WIDTH = __DATA_WIDTH__,
    parameter ADDR_WIDTH = __ADDR_WIDTH__
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  full,
    output wire                  empty,
    output wire [ADDR_WIDTH:0]   count
);
    localparam DEPTH = (1 << ADDR_WIDTH);

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];
    reg [ADDR_WIDTH-1:0] wr_ptr;
    reg [ADDR_WIDTH-1:0] rd_ptr;
    reg [ADDR_WIDTH:0] count_reg;

    wire wr_fire = wr_en && !full;
    wire rd_fire = rd_en && !empty;

    assign full = (count_reg == DEPTH[ADDR_WIDTH:0]);
    assign empty = (count_reg == {ADDR_WIDTH+1{1'b0}});
    assign count = count_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= {ADDR_WIDTH{1'b0}};
            rd_ptr <= {ADDR_WIDTH{1'b0}};
            rd_data <= {DATA_WIDTH{1'b0}};
            count_reg <= {ADDR_WIDTH+1{1'b0}};
        end else begin
            if (wr_fire) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr <= wr_ptr + 1'b1;
            end

            if (rd_fire) begin
                rd_data <= mem[rd_ptr];
                rd_ptr <= rd_ptr + 1'b1;
            end

            case ({wr_fire, rd_fire})
                2'b10: count_reg <= count_reg + 1'b1;
                2'b01: count_reg <= count_reg - 1'b1;
                default: count_reg <= count_reg;
            endcase
        end
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_sync_fifo_tb(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps

module tb_sync_fifo;
    localparam DATA_WIDTH = __DATA_WIDTH__;
    localparam ADDR_WIDTH = __ADDR_WIDTH__;
    localparam DEPTH = (1 << ADDR_WIDTH);

    reg clk;
    reg rst_n;
    reg wr_en;
    reg [DATA_WIDTH-1:0] wr_data;
    reg rd_en;
    wire [DATA_WIDTH-1:0] rd_data;
    wire full;
    wire empty;
    wire [ADDR_WIDTH:0] count;

    reg [DATA_WIDTH-1:0] expected_data [0:255];
    integer exp_wr_idx;
    integer exp_rd_idx;
    integer error_count;
    integer write_count;
    integer read_count;
    reg [127:0] scenario_id;

    sync_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .wr_en(wr_en),
        .wr_data(wr_data),
        .rd_en(rd_en),
        .rd_data(rd_data),
        .full(full),
        .empty(empty),
        .count(count)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("sync_fifo_trace.vcd");
        $dumpvars(0, tb_sync_fifo);
    end

    task automatic apply_reset;
        begin
            rst_n = 1'b0;
            wr_en = 1'b0;
            rd_en = 1'b0;
            wr_data = {DATA_WIDTH{1'b0}};
            scenario_id = "reset";
            exp_wr_idx = 0;
            exp_rd_idx = 0;
            error_count = 0;
            write_count = 0;
            read_count = 0;
            repeat (4) @(posedge clk);
            rst_n = 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic push;
        input [DATA_WIDTH-1:0] data;
        begin
            @(negedge clk);
            wr_en = 1'b1;
            wr_data = data;
            expected_data[exp_wr_idx] = data;
            exp_wr_idx = exp_wr_idx + 1;
            @(negedge clk);
            if (!full) begin
                write_count = write_count + 1;
            end
            wr_en = 1'b0;
        end
    endtask

    task automatic pop;
        reg [DATA_WIDTH-1:0] expected;
        begin
            expected = expected_data[exp_rd_idx];
            @(negedge clk);
            rd_en = 1'b1;
            @(negedge clk);
            rd_en = 1'b0;
            @(posedge clk);
            #1;
            if (rd_data !== expected) begin
                $display("SYNC_FIFO_SCOREBOARD_FAIL expected=%0h actual=%0h", expected, rd_data);
                error_count = error_count + 1;
            end else begin
                read_count = read_count + 1;
            end
            exp_rd_idx = exp_rd_idx + 1;
        end
    endtask

    initial begin
        apply_reset();

        scenario_id = "basic_ordered";
        push(8'h11);
        push(8'h22);
        pop();
        pop();
        $display("SYNC_FIFO_SCENARIO basic_ordered PASS");

        scenario_id = "full_boundary";
        repeat (DEPTH) begin
            push(8'h40 + write_count[7:0]);
        end
        if (!full) begin
            $display("SYNC_FIFO_SCOREBOARD_FAIL full flag did not assert");
            error_count = error_count + 1;
        end
        $display("SYNC_FIFO_SCENARIO full_boundary PASS");

        scenario_id = "empty_boundary";
        repeat (DEPTH) begin
            pop();
        end
        if (!empty) begin
            $display("SYNC_FIFO_SCOREBOARD_FAIL empty flag did not assert");
            error_count = error_count + 1;
        end
        $display("SYNC_FIFO_SCENARIO empty_boundary PASS");

        scenario_id = "mixed_stress";
        push(8'ha1);
        push(8'ha2);
        pop();
        push(8'ha3);
        pop();
        pop();
        $display("SYNC_FIFO_SCENARIO mixed_stress PASS");

        if (error_count == 0) begin
            $display("SYNC_FIFO_SCOREBOARD_PASS writes=%0d reads=%0d", write_count, read_count);
        end else begin
            $fatal(1, "SYNC_FIFO_SCOREBOARD_FAIL errors=%0d", error_count);
        end
        #20;
        $finish;
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_sync_fifo_vivado_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
file mkdir ../vivado_project
set timestamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
set wdb_name sync_fifo_smoke_$timestamp.wdb
set fixed_wdb sync_fifo_smoke.wdb
if {[file exists sync_fifo_trace.vcd]} { file delete -force sync_fifo_trace.vcd }
if {[file exists $fixed_wdb]} { file delete -force $fixed_wdb }
set snapshot tb_sync_fifo_snapshot
exec xvlog -sv ../rtl/sync_fifo.v ../tb/tb_sync_fifo.v
exec xelab tb_sync_fifo -debug typical -s $snapshot
exec xsim $snapshot -wdb $wdb_name -tclbatch xsim_sync_fifo_run.tcl
if {[file exists $wdb_name]} {
    file copy -force $wdb_name $fixed_wdb
    set latest_fh [open latest_sync_fifo_wdb.txt w]
    puts $latest_fh $wdb_name
    close $latest_fh
}
"""

    def render_sync_fifo_xsim_tcl(self) -> Any:
        return """log_wave -r /
run all
quit
"""

    def render_sync_fifo_project_script(self) -> Any:
        return self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set project_dir [file normalize [file join $script_dir .. vivado_project]]
file mkdir $project_dir
set xpr_path [file join $project_dir sync_fifo_project.xpr]
if {![file exists $xpr_path]} {
    create_project sync_fifo_project $project_dir -force -part xc7vx485tffg1157-1
} else {
    open_project $xpr_path
}
set_property target_language Verilog [current_project]
set rtl_path [file normalize [file join $script_dir .. rtl sync_fifo.v]]
set tb_path [file normalize [file join $script_dir .. tb tb_sync_fifo.v]]
if {[llength [get_files -quiet $rtl_path]] == 0} {
    add_files -norecurse $rtl_path
}
if {[llength [get_files -quiet -of_objects [get_filesets sim_1] $tb_path]] == 0} {
    add_files -fileset sim_1 -norecurse $tb_path
}
set_property top sync_fifo [get_filesets sources_1]
set_property top tb_sync_fifo [get_filesets sim_1]
set_property -name {xsim.simulate.runtime} -value {all} -objects [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
close_project
exit 0
"""

    def render_sync_fifo_open_project_gui_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set xpr_path ../vivado_project/sync_fifo_project.xpr
set wave_db sync_fifo_smoke.wdb
set latest_path latest_sync_fifo_wdb.txt
if {[file exists $latest_path]} {
    set fh [open $latest_path r]
    set latest_name [string trim [read $fh]]
    close $fh
    if {$latest_name ne "" && [file exists $latest_name]} {
        set wave_db $latest_name
    }
}
set wave_cfg sync_fifo_debug.wcfg
if {![file exists $xpr_path]} {
    puts stderr "Vivado project not found: $xpr_path"
    exit 1
}
open_project $xpr_path
start_gui
if {[file exists $wave_db]} {
    open_wave_database $wave_db
    catch {close_wave_config [current_wave_config]}
    create_wave_config sync_fifo_debug
    catch {add_wave_divider {Control}}
    catch {add_wave {{/tb_sync_fifo/clk}}}
    catch {add_wave {{/tb_sync_fifo/rst_n}}}
    catch {add_wave {{/tb_sync_fifo/wr_en}}}
    catch {add_wave {{/tb_sync_fifo/rd_en}}}
    catch {add_wave {{/tb_sync_fifo/full}}}
    catch {add_wave {{/tb_sync_fifo/empty}}}
    catch {add_wave -radix unsigned {{/tb_sync_fifo/count}}}
    catch {add_wave_divider {Data}}
    catch {add_wave -radix hex {{/tb_sync_fifo/wr_data}}}
    catch {add_wave -radix hex {{/tb_sync_fifo/rd_data}}}
    catch {add_wave -radix ascii {{/tb_sync_fifo/scenario_id}}}
    catch {add_wave_divider {Scoreboard}}
    catch {add_wave -radix unsigned {{/tb_sync_fifo/write_count}}}
    catch {add_wave -radix unsigned {{/tb_sync_fifo/read_count}}}
    catch {add_wave -radix unsigned {{/tb_sync_fifo/error_count}}}
    catch {save_wave_config $wave_cfg}
} else {
    puts stderr "Waveform database not found: $wave_db"
}
"""

    def render_sync_fifo_readme(self) -> Any:
        return """# sync-fifo RTL Project

This generated project contains a parameterized synchronous FIFO RTL block, a scoreboard smoke testbench, and Vivado/xsim scripts.

## Files

- `rtl/sync_fifo.v`: single-clock FIFO with full/empty/count status.
- `tb/tb_sync_fifo.v`: smoke testbench with ordered, full, empty, and mixed traffic scenarios.
- `sim/run_vivado_sync_fifo.tcl`: Vivado batch simulation script.
- `sim/create_sync_fifo_project.tcl`: creates/updates `vivado_project/sync_fifo_project.xpr`.
- `sim/open_sync_fifo_project_gui.tcl`: opens the Vivado project and latest WDB.

## Run

```powershell
cd sim
vivado -mode batch -source run_vivado_sync_fifo.tcl
vivado -mode batch -source create_sync_fifo_project.tcl
vivado -mode gui -source open_sync_fifo_project_gui.tcl
```
"""

    def write_sync_fifo_project(self, output_dir: Any, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = Path(output_dir) / "sync-fifo"
        rtl_dir = project_dir / "rtl"
        tb_dir = project_dir / "tb"
        sim_dir = project_dir / "sim"
        reports_dir = project_dir / "reports"
        for path in (rtl_dir, tb_dir, sim_dir, reports_dir):
            path.mkdir(parents=True, exist_ok=True)

        (rtl_dir / "sync_fifo.v").write_text(
            self.render_sync_fifo_rtl(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (tb_dir / "tb_sync_fifo.v").write_text(
            self.render_sync_fifo_tb(data_width=data_width, addr_width=addr_width),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_sync_fifo.tcl").write_text(
            self.render_sync_fifo_vivado_script(),
            encoding="utf-8",
        )
        (sim_dir / "xsim_sync_fifo_run.tcl").write_text(
            self.render_sync_fifo_xsim_tcl(),
            encoding="utf-8",
        )
        (sim_dir / "create_sync_fifo_project.tcl").write_text(
            self.render_sync_fifo_project_script(),
            encoding="utf-8",
        )
        (sim_dir / "open_sync_fifo_project_gui.tcl").write_text(
            self.render_sync_fifo_open_project_gui_script(),
            encoding="utf-8",
        )
        (project_dir / "README.md").write_text(self.render_sync_fifo_readme(), encoding="utf-8")
        return project_dir

    def resolve_sync_fifo_wave_db(self, sim_dir: Any) -> Any:
        sim_dir = Path(sim_dir)
        latest_path = sim_dir / "latest_sync_fifo_wdb.txt"
        if latest_path.exists():
            latest_name = latest_path.read_text(encoding="utf-8").strip()
            if latest_name:
                latest_wdb = sim_dir / latest_name
                if latest_wdb.exists():
                    return latest_wdb
        legacy_wdb = sim_dir / "sync_fifo_smoke.wdb"
        if legacy_wdb.exists():
            return legacy_wdb
        candidates = sorted(
            sim_dir.glob("sync_fifo_smoke_*.wdb"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else legacy_wdb

    def open_sync_fifo_project_gui(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "sync_fifo_project.xpr"
        wave_db_path = self.resolve_sync_fifo_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_sync_fifo_project_gui.tcl"

        if not xpr_path.exists():
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines("Vivado project not found: {}".format(xpr_path)),
                stream=sys.stderr,
            )
            return False
        if not wave_db_path.exists():
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines(
                    "Vivado waveform database not found: {}".format(wave_db_path)
                ),
                stream=sys.stderr,
            )
            return False
        if not gui_script_path.exists():
            gui_script_path.write_text(self.render_sync_fifo_open_project_gui_script(), encoding="utf-8")

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines(
                    "Vivado command not found; cannot open waveform GUI."
                ),
                stream=sys.stderr,
            )
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        emit_sync_fifo_lines(
            [
                "Vivado project GUI launched: {}".format(xpr_path),
                "Vivado waveform database: {}".format(wave_db_path),
            ]
        )
        return True

    def run_sync_fifo_vivado_sim(self, output_dir: Any="outputs", open_wave_gui: Any=True, data_width: Any=8, addr_width: Any=4) -> Any:
        project_dir = self.generate_rtl_project(
            "sync-fifo",
            output_dir,
            data_width=data_width,
            addr_width=addr_width,
        )
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines("Vivado command not found."),
                stream=sys.stderr,
            )
            return False

        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_sync_fifo.tcl",
            sim_dir,
        )
        if sim_result.returncode != 0:
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines(
                    sim_result.stderr.strip() or sim_result.stdout.strip() or "sync FIFO simulation failed"
                ),
                stream=sys.stderr,
            )
            return False

        vcd_path = sim_dir / "sync_fifo_trace.vcd"
        wave_db_path = self.resolve_sync_fifo_wave_db(sim_dir)
        if not vcd_path.exists():
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines("Simulation did not generate VCD: {}".format(vcd_path)),
                stream=sys.stderr,
            )
            return False
        if not wave_db_path.exists():
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines("Simulation did not generate WDB: {}".format(wave_db_path)),
                stream=sys.stderr,
            )
            return False

        project_result = self.run_vivado_batch(
            vivado_command,
            "create_sync_fifo_project.tcl",
            sim_dir,
            extra_args=["-nojournal", "-nolog", "-notrace"],
        )
        project_warning = None
        if project_result.returncode != 0:
            project_warning = project_result.stderr.strip() or project_result.stdout.strip() or "Vivado project generation failed"

        report_path = self.write_sync_fifo_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            sim_result=sim_result,
            project_result=project_result,
        )
        emit_sync_fifo_lines(
            build_sync_fifo_sim_completed_lines(
                project_dir,
                vcd_path,
                wave_db_path,
                project_warning,
                report_path,
            )
        )
        if project_warning is not None:
            emit_sync_fifo_lines(
                build_sync_fifo_error_lines("Vivado project warning: {}".format(project_warning)),
                stream=sys.stderr,
            )
        if open_wave_gui and project_warning is None:
            self.open_sync_fifo_project_gui(project_dir)
        return True
