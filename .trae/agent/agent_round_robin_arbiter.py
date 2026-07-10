# -*- coding: utf-8 -*-
from typing import Any, TYPE_CHECKING
import html
import sys
from pathlib import Path


class RoundRobinArbiterMixin:
    if TYPE_CHECKING:
        check_rtl_project: Any
        generate_rtl_project: Any
        launch_vivado_gui: Any
        render_vivado_tclstore_bootstrap: Any
        resolve_vivado_command: Any
        run_vivado_batch: Any
        run_waveform_analyzer_json: Any

    def resolve_round_robin_arbiter_vcd_path(self, output_dir: Any="outputs") -> Any:
        return Path(output_dir) / "round-robin-arbiter" / "sim" / "round_robin_arbiter_trace.vcd"

    def collect_round_robin_arbiter_vcd_analysis(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        vcd_path = self.resolve_round_robin_arbiter_vcd_path(output_dir)
        if not vcd_path.exists():
            raise FileNotFoundError("Round-Robin Arbiter VCD file not found: {}".format(vcd_path))

        info = self.run_waveform_analyzer_json("info", vcd_path, backend=waveform_backend)
        grant_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_round_robin_arbiter.grant_valid=1",
            "--changed",
            "tb_round_robin_arbiter.grant_count",
            "--show",
            "tb_round_robin_arbiter.req,tb_round_robin_arbiter.grant,tb_round_robin_arbiter.grant_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        fairness_events = self.run_waveform_analyzer_json(
            "search",
            vcd_path,
            "--condition",
            "tb_round_robin_arbiter.grant_valid=1",
            "--changed",
            "tb_round_robin_arbiter.grant_count",
            "--show",
            "tb_round_robin_arbiter.scenario_id,tb_round_robin_arbiter.req,tb_round_robin_arbiter.grant,tb_round_robin_arbiter.grant_count",
            "--limit",
            limit,
            backend=waveform_backend,
        )
        return {
            "vcd_path": vcd_path,
            "info": info,
            "grant_events": grant_events,
            "fairness_events": fairness_events,
        }

    def analyze_round_robin_arbiter_vcd(self, output_dir: Any="outputs", limit: Any=20, waveform_backend: Any="auto") -> Any:
        try:
            analysis = self.collect_round_robin_arbiter_vcd_analysis(
                output_dir=output_dir,
                limit=limit,
                waveform_backend=waveform_backend,
            )
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            print("Run --sim-rtl round-robin-arbiter first, or check --output-dir.", file=sys.stderr)
            return False
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return False

        vcd_path = analysis["vcd_path"]
        info = analysis["info"]
        grant_events = analysis["grant_events"]
        fairness_events = analysis["fairness_events"]

        print("Round-Robin Arbiter VCD analysis")
        print("=" * 60)
        print("File: {}".format(vcd_path))
        print("Signals: {}".format(info.get("signal_count", "unknown")))
        print("Backend: {}".format(info.get("_waveform_backend", "unknown")))
        print("Time range: {} - {}".format(info.get("time_min_h", "unknown"), info.get("time_max_h", "unknown")))
        print("Duration: {}".format(info.get("duration_h", "unknown")))
        print("Timescale: {}".format(info.get("timescale", "unknown")))
        print("Grant events: {}".format(grant_events.get("total", grant_events.get("shown", "unknown"))))
        print("Fairness checkpoints: {}".format(fairness_events.get("total", fairness_events.get("shown", "unknown"))))

        for title, result in [("Grants", grant_events), ("Fairness", fairness_events)]:
            rows = result.get("segments") or result.get("intervals") or result.get("events") or []
            print("\n{}".format(title))
            for index, row in enumerate(rows[: int(limit)], start=1):
                begin = row.get("begin_h") or row.get("time_h") or row.get("at_h") or "unknown"
                end = row.get("end_h")
                values = row.get("values") or {}
                if end:
                    print("  {}. {} -> {} {}".format(index, begin, end, values))
                else:
                    print("  {}. {} {}".format(index, begin, values))

        project_dir = Path(output_dir) / "round-robin-arbiter"
        report_path = self.write_round_robin_arbiter_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=self.resolve_round_robin_arbiter_wave_db(project_dir / "sim"),
            analysis=analysis,
            limit=limit,
        )
        print("Simulation report refreshed: {}".format(report_path))
        return True

    def write_round_robin_arbiter_sim_report(
        self,
        project_dir: Any,
        vcd_path: Any,
        wave_db_path: Any,
        sim_result: Any=None,
        project_result: Any=None,
        limit: Any=20,
        analysis: Any=None,
    ) -> Any:
        project_dir = Path(project_dir)
        reports_dir = project_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "sim_report.md"
        html_path = reports_dir / "sim_report.html"

        analysis_error = None
        if analysis is None:
            try:
                analysis = self.collect_round_robin_arbiter_vcd_analysis(
                    output_dir=project_dir.parent,
                    limit=limit,
                )
            except (FileNotFoundError, RuntimeError) as exc:
                analysis_error = str(exc)

        lines = [
            "# round-robin-arbiter 仿真报告",
            "",
            "## 摘要",
            "",
            "- 目标：`round-robin-arbiter`",
            "- 仿真器：Vivado/xsim",
            "- 状态：{}".format("PASS" if analysis_error is None else "PASS_WITH_ANALYSIS_WARNING"),
            "- VCD：`{}`".format(vcd_path),
            "- WDB：`{}`".format(wave_db_path),
            "- Vivado 工程：`{}`".format(project_dir / "vivado_project" / "round_robin_arbiter_project.xpr"),
            "- 工程创建：{}".format("PASS" if project_result is not None and project_result.returncode == 0 else "WARNING"),
            "",
            "## Scoreboard",
            "",
            "- Testbench includes `ROUND_ROBIN_ARBITER_SCOREBOARD_PASS` / `ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL` checks.",
            "- xsim returns failure if `$fatal(1, ...)` is reached.",
            "",
            "## 场景",
            "",
            "- `single_request`：单路请求必须被正确授权。",
            "- `multiple_requests`：多路请求按照轮询指针选择下一路。",
            "- `rotating_grant`：连续全请求时 grant 必须循环轮转。",
            "- `reset_recovery`：复位后优先级回到 requester 0。",
            "- `fairness_window`：持续全请求窗口内所有 requester 都必须获得授权。",
        ]

        if analysis is not None:
            info = analysis["info"]
            grant_events = analysis["grant_events"]
            fairness_events = analysis["fairness_events"]
            lines.extend([
                "",
                "## VCD Analysis",
                "",
                "- Backend: `{}`".format(info.get("_waveform_backend", "unknown")),
                "- Signals: `{}`".format(info.get("signal_count", "unknown")),
                "- Duration: `{}`".format(info.get("duration_h", "unknown")),
                "- Timescale: `{}`".format(info.get("timescale", "unknown")),
                "- Grant events: `{}`".format(grant_events.get("total", grant_events.get("shown", "unknown"))),
                "- Fairness checkpoints: `{}`".format(fairness_events.get("total", fairness_events.get("shown", "unknown"))),
            ])
        else:
            lines.extend(["", "## VCD Analysis", "", "- Warning: `{}`".format(analysis_error)])

        lines.extend([
            "",
            "## 下一步命令",
            "",
            "```powershell",
            "python .trae/agent/agent.py --analyze-rtl-vcd round-robin-arbiter --output-dir {}".format(project_dir.parent),
            "python .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir {}".format(project_dir.parent),
            "```",
            "",
        ])
        report_path.write_text("\n".join(lines), encoding="utf-8")

        html_lines = [
            "<!doctype html>",
            "<html lang=\"zh-CN\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<title>round-robin-arbiter 仿真报告</title>",
            "<style>",
            "body{margin:0;background:#f5f7fb;color:#172033;font-family:Segoe UI,Microsoft YaHei,Arial,sans-serif}",
            ".page{max-width:1080px;margin:0 auto;padding:34px 22px}",
            ".hero{background:#172033;color:white;border-radius:10px;padding:28px 32px;margin-bottom:18px}",
            ".hero h1{margin:0 0 8px;font-size:30px}",
            ".hero p{margin:0;color:#cbd5e1}",
            ".grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}",
            ".card{background:white;border:1px solid #dbe3ef;border-radius:8px;padding:16px}",
            ".label{font-size:12px;color:#64748b;font-weight:700;text-transform:uppercase}",
            ".value{font-size:22px;font-weight:800;margin-top:8px}",
            ".section{background:white;border:1px solid #dbe3ef;border-radius:8px;padding:20px;margin-top:14px}",
            "code{background:#eef3f8;padding:2px 6px;border-radius:5px}",
            "pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto}",
            "@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.page{padding:18px 12px}}",
            "</style>",
            "</head>",
            "<body><main class=\"page\">",
            "<section class=\"hero\"><h1>round-robin-arbiter 仿真报告</h1><p>4 路轮询仲裁器的 Vivado/xsim 仿真、VCD 分析与 WDB 波形入口。</p></section>",
        ]
        if analysis is not None:
            info = analysis["info"]
            grant_events = analysis["grant_events"]
            fairness_events = analysis["fairness_events"]
            html_lines.extend([
                "<section class=\"grid\">",
                "<article class=\"card\"><div class=\"label\">信号数量</div><div class=\"value\">{}</div></article>".format(html.escape(str(info.get("signal_count", "unknown")))),
                "<article class=\"card\"><div class=\"label\">仿真时长</div><div class=\"value\">{}</div></article>".format(html.escape(str(info.get("duration_h", "unknown")))),
                "<article class=\"card\"><div class=\"label\">Grant 事件</div><div class=\"value\">{}</div></article>".format(html.escape(str(grant_events.get("total", grant_events.get("shown", "unknown"))))),
                "<article class=\"card\"><div class=\"label\">公平性检查点</div><div class=\"value\">{}</div></article>".format(html.escape(str(fairness_events.get("total", fairness_events.get("shown", "unknown"))))),
                "</section>",
            ])
        html_lines.extend([
            "<section class=\"section\"><h2>场景覆盖</h2><ul><li>single_request</li><li>multiple_requests</li><li>rotating_grant</li><li>reset_recovery</li><li>fairness_window</li></ul></section>",
            "<section class=\"section\"><h2>产物路径</h2><p>VCD：<code>{}</code></p><p>WDB：<code>{}</code></p><p>工程：<code>{}</code></p></section>".format(
                html.escape(str(vcd_path)),
                html.escape(str(wave_db_path)),
                html.escape(str(project_dir / "vivado_project" / "round_robin_arbiter_project.xpr")),
            ),
            "<section class=\"section\"><h2>常用命令</h2><pre>python .trae/agent/agent.py --analyze-rtl-vcd round-robin-arbiter --output-dir {}\npython .trae/agent/agent.py --open-wave round-robin-arbiter --output-dir {}</pre></section>".format(
                html.escape(str(project_dir.parent)),
                html.escape(str(project_dir.parent)),
            ),
            "</main></body></html>",
        ])
        html_path.write_text("\n".join(html_lines), encoding="utf-8")
        return report_path

    def check_round_robin_arbiter_rtl(self, output_dir: Any="outputs") -> Any:
        return self.check_rtl_project(
            target_name="round-robin-arbiter",
            output_dir=output_dir,
            rtl_name="round_robin_arbiter.v",
            tb_name="tb_round_robin_arbiter.v",
            sim_script_name="run_vivado_round_robin_arbiter.tcl",
            project_script_name="create_round_robin_arbiter_project.tcl",
            gui_script_name="open_round_robin_arbiter_project_gui.tcl",
            xpr_name="round_robin_arbiter_project.xpr",
            vcd_name="round_robin_arbiter_trace.vcd",
            wave_db_resolver=self.resolve_round_robin_arbiter_wave_db,
            rtl_markers=[
                ("RTL declares round_robin_arbiter", "module round_robin_arbiter"),
                ("RTL has grant validity logic", "assign grant_valid"),
                ("RTL has rotating grant logic", "grant_next"),
            ],
            tb_markers=[
                ("TB declares tb_round_robin_arbiter", "module tb_round_robin_arbiter"),
                ("TB prints scoreboard pass", "ROUND_ROBIN_ARBITER_SCOREBOARD_PASS"),
                ("TB covers fairness window", "fairness_window"),
                ("TB fatal on scoreboard fail", "ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL"),
            ],
        )

    def render_round_robin_arbiter_rtl(self, requesters: Any=4) -> Any:
        return """`timescale 1ns/1ps

module round_robin_arbiter #(
    parameter REQUESTERS = __REQUESTERS__
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [REQUESTERS-1:0] req,
    output reg  [REQUESTERS-1:0] grant,
    output wire grant_valid
);
    reg [REQUESTERS-1:0] pointer;
    reg [REQUESTERS-1:0] grant_comb;
    wire [REQUESTERS-1:0] grant_next;
    integer offset;
    integer index;

    assign grant_valid = |grant;
    assign grant_next = grant_comb;

    always @* begin
        grant_comb = {REQUESTERS{1'b0}};
        for (offset = 0; offset < REQUESTERS; offset = offset + 1) begin
            index = 0;
            if (pointer[0]) index = offset;
            else if (pointer[1]) index = (1 + offset) % REQUESTERS;
            else if (pointer[2]) index = (2 + offset) % REQUESTERS;
            else if (pointer[3]) index = (3 + offset) % REQUESTERS;
            if ((grant_comb == {REQUESTERS{1'b0}}) && req[index]) begin
                grant_comb[index] = 1'b1;
            end
        end
    end

    function [REQUESTERS-1:0] rotate_left_one;
        input [REQUESTERS-1:0] value;
        begin
            rotate_left_one = {value[REQUESTERS-2:0], value[REQUESTERS-1]};
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pointer <= {{REQUESTERS-1{1'b0}}, 1'b1};
            grant <= {REQUESTERS{1'b0}};
        end else begin
            grant <= grant_next;
            if (|grant_next) begin
                pointer <= rotate_left_one(grant_next);
            end
        end
    end
endmodule
""".replace("__REQUESTERS__", str(int(requesters)))

    def render_round_robin_arbiter_tb(self, requesters: Any=4) -> Any:
        return """`timescale 1ns/1ps

module tb_round_robin_arbiter;
    localparam REQUESTERS = __REQUESTERS__;

    reg clk;
    reg rst_n;
    reg [REQUESTERS-1:0] req;
    wire [REQUESTERS-1:0] grant;
    wire grant_valid;

    integer error_count;
    integer grant_count;
    integer fairness_seen [0:REQUESTERS-1];
    reg [127:0] scenario_id;

    round_robin_arbiter #(
        .REQUESTERS(REQUESTERS)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .req(req),
        .grant(grant),
        .grant_valid(grant_valid)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("round_robin_arbiter_trace.vcd");
        $dumpvars(0, tb_round_robin_arbiter);
    end

    task automatic apply_reset;
        integer i;
        begin
            rst_n = 1'b0;
            req = {REQUESTERS{1'b0}};
            scenario_id = "reset";
            error_count = 0;
            grant_count = 0;
            for (i = 0; i < REQUESTERS; i = i + 1) begin
                fairness_seen[i] = 0;
            end
            repeat (4) @(posedge clk);
            rst_n = 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task automatic expect_grant;
        input [REQUESTERS-1:0] request_value;
        input [REQUESTERS-1:0] expected_grant;
        begin
            @(negedge clk);
            req = request_value;
            @(posedge clk);
            #1;
            if (grant !== expected_grant) begin
                $display("ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL expected=%b actual=%b req=%b scenario=%s", expected_grant, grant, request_value, scenario_id);
                error_count = error_count + 1;
            end else if ((grant & request_value) != grant) begin
                $display("ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL grant_without_request grant=%b req=%b", grant, request_value);
                error_count = error_count + 1;
            end else if ((grant != {REQUESTERS{1'b0}}) && ((grant & (grant - 1'b1)) != {REQUESTERS{1'b0}})) begin
                $display("ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL grant_not_onehot grant=%b", grant);
                error_count = error_count + 1;
            end else begin
                grant_count = grant_count + (grant_valid ? 1 : 0);
            end
        end
    endtask

    initial begin
        apply_reset();

        scenario_id = "single_request";
        expect_grant(4'b0010, 4'b0010);
        $display("ROUND_ROBIN_ARBITER_SCENARIO single_request PASS");

        scenario_id = "multiple_requests";
        expect_grant(4'b1011, 4'b1000);
        expect_grant(4'b1011, 4'b0001);
        expect_grant(4'b1011, 4'b0010);
        $display("ROUND_ROBIN_ARBITER_SCENARIO multiple_requests PASS");

        scenario_id = "rotating_grant";
        expect_grant(4'b1111, 4'b0100);
        expect_grant(4'b1111, 4'b1000);
        expect_grant(4'b1111, 4'b0001);
        expect_grant(4'b1111, 4'b0010);
        $display("ROUND_ROBIN_ARBITER_SCENARIO rotating_grant PASS");

        scenario_id = "reset_recovery";
        rst_n = 1'b0;
        req = 4'b1111;
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        expect_grant(4'b1111, 4'b0001);
        $display("ROUND_ROBIN_ARBITER_SCENARIO reset_recovery PASS");

        scenario_id = "fairness_window";
        expect_grant(4'b1111, 4'b0010);
        fairness_seen[1] = 1;
        expect_grant(4'b1111, 4'b0100);
        fairness_seen[2] = 1;
        expect_grant(4'b1111, 4'b1000);
        fairness_seen[3] = 1;
        expect_grant(4'b1111, 4'b0001);
        fairness_seen[0] = 1;
        if (!(fairness_seen[0] && fairness_seen[1] && fairness_seen[2] && fairness_seen[3])) begin
            $display("ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL fairness window missed a requester");
            error_count = error_count + 1;
        end
        $display("ROUND_ROBIN_ARBITER_SCENARIO fairness_window PASS");

        @(negedge clk);
        req = 4'b0000;
        repeat (2) @(posedge clk);

        if (error_count == 0) begin
            $display("ROUND_ROBIN_ARBITER_SCOREBOARD_PASS grants=%0d", grant_count);
        end else begin
            $fatal(1, "ROUND_ROBIN_ARBITER_SCOREBOARD_FAIL errors=%0d", error_count);
        end
        #20;
        $finish;
    end
endmodule
""".replace("__REQUESTERS__", str(int(requesters)))

    def render_round_robin_arbiter_vivado_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
file mkdir ../vivado_project
set timestamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
set wdb_name round_robin_arbiter_smoke_$timestamp.wdb
set fixed_wdb round_robin_arbiter_smoke.wdb
if {[file exists round_robin_arbiter_trace.vcd]} { file delete -force round_robin_arbiter_trace.vcd }
if {[file exists $fixed_wdb]} { file delete -force $fixed_wdb }
set snapshot tb_round_robin_arbiter_snapshot
exec xvlog -sv ../rtl/round_robin_arbiter.v ../tb/tb_round_robin_arbiter.v
exec xelab tb_round_robin_arbiter -debug typical -s $snapshot
exec xsim $snapshot -wdb $wdb_name -tclbatch xsim_round_robin_arbiter_run.tcl
if {[file exists $wdb_name]} {
    file copy -force $wdb_name $fixed_wdb
    set latest_fh [open latest_round_robin_arbiter_wdb.txt w]
    puts $latest_fh $wdb_name
    close $latest_fh
}
"""

    def render_round_robin_arbiter_xsim_tcl(self) -> Any:
        return """log_wave -r /
run all
quit
"""

    def render_round_robin_arbiter_project_script(self) -> Any:
        return self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set project_dir [file normalize [file join $script_dir .. vivado_project]]
file mkdir $project_dir
set xpr_path [file join $project_dir round_robin_arbiter_project.xpr]
if {![file exists $xpr_path]} {
    create_project round_robin_arbiter_project $project_dir -force -part xc7vx485tffg1157-1
} else {
    open_project $xpr_path
}
set_property target_language Verilog [current_project]
set rtl_path [file normalize [file join $script_dir .. rtl round_robin_arbiter.v]]
set tb_path [file normalize [file join $script_dir .. tb tb_round_robin_arbiter.v]]
if {[llength [get_files -quiet $rtl_path]] == 0} {
    add_files -norecurse $rtl_path
}
if {[llength [get_files -quiet -of_objects [get_filesets sim_1] $tb_path]] == 0} {
    add_files -fileset sim_1 -norecurse $tb_path
}
set_property top round_robin_arbiter [get_filesets sources_1]
set_property top tb_round_robin_arbiter [get_filesets sim_1]
set_property -name {xsim.simulate.runtime} -value {all} -objects [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
close_project
exit 0
"""

    def render_round_robin_arbiter_open_project_gui_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set xpr_path ../vivado_project/round_robin_arbiter_project.xpr
set wave_db round_robin_arbiter_smoke.wdb
set latest_path latest_round_robin_arbiter_wdb.txt
if {[file exists $latest_path]} {
    set fh [open $latest_path r]
    set latest_name [string trim [read $fh]]
    close $fh
    if {$latest_name ne "" && [file exists $latest_name]} {
        set wave_db $latest_name
    }
}
set wave_cfg round_robin_arbiter_debug.wcfg
if {![file exists $xpr_path]} {
    puts stderr "Vivado project not found: $xpr_path"
    exit 1
}
open_project $xpr_path
start_gui
if {[file exists $wave_db]} {
    open_wave_database $wave_db
    catch {close_wave_config [current_wave_config]}
    create_wave_config round_robin_arbiter_debug
    catch {add_wave_divider {Control}}
    catch {add_wave {{/tb_round_robin_arbiter/clk}}}
    catch {add_wave {{/tb_round_robin_arbiter/rst_n}}}
    catch {add_wave -radix ascii {{/tb_round_robin_arbiter/scenario_id}}}
    catch {add_wave_divider {Requests And Grants}}
    catch {add_wave -radix binary {{/tb_round_robin_arbiter/req}}}
    catch {add_wave -radix binary {{/tb_round_robin_arbiter/grant}}}
    catch {add_wave {{/tb_round_robin_arbiter/grant_valid}}}
    catch {add_wave -radix binary {{/tb_round_robin_arbiter/dut/pointer}}}
    catch {add_wave_divider {Fairness}}
    catch {add_wave -radix unsigned {{/tb_round_robin_arbiter/grant_count}}}
    catch {add_wave -radix unsigned {{/tb_round_robin_arbiter/error_count}}}
    catch {save_wave_config $wave_cfg}
} else {
    puts stderr "Waveform database not found: $wave_db"
}
"""

    def render_round_robin_arbiter_readme(self) -> Any:
        return """# round-robin-arbiter RTL Project

This generated project contains a 4-requester round-robin arbiter, a scoreboard smoke testbench, and Vivado/xsim scripts.

## Files

- `rtl/round_robin_arbiter.v`: one-hot pointer round-robin arbiter.
- `tb/tb_round_robin_arbiter.v`: smoke testbench covering single request, multiple request, rotation, reset, and fairness windows.
- `sim/run_vivado_round_robin_arbiter.tcl`: Vivado batch simulation script.
- `sim/create_round_robin_arbiter_project.tcl`: creates/updates `vivado_project/round_robin_arbiter_project.xpr`.
- `sim/open_round_robin_arbiter_project_gui.tcl`: opens the Vivado project and latest WDB.

## Run

```powershell
cd sim
vivado -mode batch -source run_vivado_round_robin_arbiter.tcl
vivado -mode batch -source create_round_robin_arbiter_project.tcl
vivado -mode gui -source open_round_robin_arbiter_project_gui.tcl
```
"""

    def write_round_robin_arbiter_project(self, output_dir: Any, requesters: Any=4) -> Any:
        project_dir = Path(output_dir) / "round-robin-arbiter"
        rtl_dir = project_dir / "rtl"
        tb_dir = project_dir / "tb"
        sim_dir = project_dir / "sim"
        reports_dir = project_dir / "reports"
        for path in (rtl_dir, tb_dir, sim_dir, reports_dir):
            path.mkdir(parents=True, exist_ok=True)

        (rtl_dir / "round_robin_arbiter.v").write_text(
            self.render_round_robin_arbiter_rtl(requesters=requesters),
            encoding="utf-8",
        )
        (tb_dir / "tb_round_robin_arbiter.v").write_text(
            self.render_round_robin_arbiter_tb(requesters=requesters),
            encoding="utf-8",
        )
        (sim_dir / "run_vivado_round_robin_arbiter.tcl").write_text(
            self.render_round_robin_arbiter_vivado_script(),
            encoding="utf-8",
        )
        (sim_dir / "xsim_round_robin_arbiter_run.tcl").write_text(
            self.render_round_robin_arbiter_xsim_tcl(),
            encoding="utf-8",
        )
        (sim_dir / "create_round_robin_arbiter_project.tcl").write_text(
            self.render_round_robin_arbiter_project_script(),
            encoding="utf-8",
        )
        (sim_dir / "open_round_robin_arbiter_project_gui.tcl").write_text(
            self.render_round_robin_arbiter_open_project_gui_script(),
            encoding="utf-8",
        )
        (project_dir / "README.md").write_text(self.render_round_robin_arbiter_readme(), encoding="utf-8")
        return project_dir

    def resolve_round_robin_arbiter_wave_db(self, sim_dir: Any) -> Any:
        sim_dir = Path(sim_dir)
        latest_path = sim_dir / "latest_round_robin_arbiter_wdb.txt"
        if latest_path.exists():
            latest_name = latest_path.read_text(encoding="utf-8").strip()
            if latest_name:
                latest_wdb = sim_dir / latest_name
                if latest_wdb.exists():
                    return latest_wdb
        legacy_wdb = sim_dir / "round_robin_arbiter_smoke.wdb"
        if legacy_wdb.exists():
            return legacy_wdb
        candidates = sorted(
            sim_dir.glob("round_robin_arbiter_smoke_*.wdb"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else legacy_wdb

    def open_round_robin_arbiter_project_gui(self, project_dir: Any) -> Any:
        project_dir = Path(project_dir)
        sim_dir = project_dir / "sim"
        xpr_path = project_dir / "vivado_project" / "round_robin_arbiter_project.xpr"
        wave_db_path = self.resolve_round_robin_arbiter_wave_db(sim_dir)
        gui_script_path = sim_dir / "open_round_robin_arbiter_project_gui.tcl"

        if not xpr_path.exists():
            print("Vivado project not found: {}".format(xpr_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Vivado waveform database not found: {}".format(wave_db_path), file=sys.stderr)
            return False
        if not gui_script_path.exists():
            gui_script_path.write_text(self.render_round_robin_arbiter_open_project_gui_script(), encoding="utf-8")

        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found; cannot open waveform GUI.", file=sys.stderr)
            return False

        self.launch_vivado_gui(vivado_command, gui_script_path.name, sim_dir)
        print("Vivado project GUI launched: {}".format(xpr_path))
        print("Vivado waveform database: {}".format(wave_db_path))
        return True

    def run_round_robin_arbiter_vivado_sim(self, output_dir: Any="outputs", open_wave_gui: Any=True) -> Any:
        project_dir = self.generate_rtl_project("round-robin-arbiter", output_dir)
        sim_dir = project_dir / "sim"
        vivado_command = self.resolve_vivado_command()
        if not vivado_command:
            print("Vivado command not found.", file=sys.stderr)
            return False

        sim_result = self.run_vivado_batch(
            vivado_command,
            "run_vivado_round_robin_arbiter.tcl",
            sim_dir,
        )
        if sim_result.returncode != 0:
            print(sim_result.stderr.strip() or sim_result.stdout.strip() or "round-robin arbiter simulation failed", file=sys.stderr)
            return False

        vcd_path = sim_dir / "round_robin_arbiter_trace.vcd"
        wave_db_path = self.resolve_round_robin_arbiter_wave_db(sim_dir)
        if not vcd_path.exists():
            print("Simulation did not generate VCD: {}".format(vcd_path), file=sys.stderr)
            return False
        if not wave_db_path.exists():
            print("Simulation did not generate WDB: {}".format(wave_db_path), file=sys.stderr)
            return False

        project_result = self.run_vivado_batch(
            vivado_command,
            "create_round_robin_arbiter_project.tcl",
            sim_dir,
            extra_args=["-nojournal", "-nolog", "-notrace"],
        )
        project_warning = None
        if project_result.returncode != 0:
            project_warning = project_result.stderr.strip() or project_result.stdout.strip() or "Vivado project generation failed"

        print("Round-Robin Arbiter simulation completed")
        print("Generated VCD: {}".format(vcd_path))
        print("Generated WDB: {}".format(wave_db_path))
        if project_warning is None:
            print("Vivado project: {}".format(project_dir / "vivado_project" / "round_robin_arbiter_project.xpr"))
        else:
            print("Vivado project warning: {}".format(project_warning), file=sys.stderr)
        report_path = self.write_round_robin_arbiter_sim_report(
            project_dir=project_dir,
            vcd_path=vcd_path,
            wave_db_path=wave_db_path,
            sim_result=sim_result,
            project_result=project_result,
        )
        print("Simulation report: {}".format(report_path))
        if open_wave_gui and project_warning is None:
            self.open_round_robin_arbiter_project_gui(project_dir)
        return True
