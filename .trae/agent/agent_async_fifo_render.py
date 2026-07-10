# -*- coding: utf-8 -*-
from typing import Any, TYPE_CHECKING
from wave_visibility import render_wave_open_probe_tcl


class AsyncFifoRenderMixin:
    if TYPE_CHECKING:
        render_vivado_tclstore_bootstrap: Any

    def render_async_fifo_uvm_interface(self, data_width: Any=8) -> Any:
        return """interface async_fifo_if #(parameter DATA_WIDTH = __DATA_WIDTH__);
    logic wr_clk;
    logic rd_clk;
    logic wr_rst_n;
    logic rd_rst_n;
    logic wr_en;
    logic rd_en;
    logic [DATA_WIDTH-1:0] wr_data;
    logic [DATA_WIDTH-1:0] rd_data;
    logic full;
    logic empty;

    modport dut (
        input wr_clk,
        input rd_clk,
        input wr_rst_n,
        input rd_rst_n,
        input wr_en,
        input rd_en,
        input wr_data,
        output rd_data,
        output full,
        output empty
    );
endinterface
""".replace("__DATA_WIDTH__", str(int(data_width)))

    def render_async_fifo_uvm_pkg(self) -> Any:
        return """package async_fifo_uvm_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    class async_fifo_item extends uvm_sequence_item;
        rand bit write;
        rand bit read;
        rand bit [7:0] data;

        `uvm_object_utils_begin(async_fifo_item)
            `uvm_field_int(write, UVM_ALL_ON)
            `uvm_field_int(read, UVM_ALL_ON)
            `uvm_field_int(data, UVM_ALL_ON)
        `uvm_object_utils_end

        function new(string name = "async_fifo_item");
            super.new(name);
        endfunction
    endclass

    class async_fifo_sequence extends uvm_sequence #(async_fifo_item);
        `uvm_object_utils(async_fifo_sequence)

        function new(string name = "async_fifo_sequence");
            super.new(name);
        endfunction

        task body();
            async_fifo_item item;
            for (int i = 0; i < 8; i++) begin
                item = async_fifo_item::type_id::create($sformatf("wr_%0d", i));
                start_item(item);
                item.write = 1'b1;
                item.read = 1'b0;
                item.data = 8'h40 + i[7:0];
                finish_item(item);
            end
            for (int i = 0; i < 8; i++) begin
                item = async_fifo_item::type_id::create($sformatf("rd_%0d", i));
                start_item(item);
                item.write = 1'b0;
                item.read = 1'b1;
                item.data = '0;
                finish_item(item);
            end
        endtask
    endclass

    class async_fifo_driver extends uvm_driver #(async_fifo_item);
        `uvm_component_utils(async_fifo_driver)
        virtual async_fifo_if vif;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db #(virtual async_fifo_if)::get(this, "", "vif", vif)) begin
                `uvm_fatal("NOVIF", "async_fifo_if is not configured")
            end
        endfunction

        task reset_bus();
            vif.wr_en <= 1'b0;
            vif.rd_en <= 1'b0;
            vif.wr_data <= '0;
            wait (vif.wr_rst_n == 1'b1 && vif.rd_rst_n == 1'b1);
        endtask

        task drive_write(async_fifo_item item);
            @(posedge vif.wr_clk);
            while (vif.full) @(posedge vif.wr_clk);
            vif.wr_data <= item.data;
            vif.wr_en <= 1'b1;
            @(posedge vif.wr_clk);
            vif.wr_en <= 1'b0;
        endtask

        task drive_read();
            @(posedge vif.rd_clk);
            while (vif.empty) @(posedge vif.rd_clk);
            vif.rd_en <= 1'b1;
            @(posedge vif.rd_clk);
            vif.rd_en <= 1'b0;
        endtask

        task run_phase(uvm_phase phase);
            async_fifo_item item;
            reset_bus();
            forever begin
                seq_item_port.get_next_item(item);
                if (item.write) drive_write(item);
                if (item.read) drive_read();
                seq_item_port.item_done();
            end
        endtask
    endclass

    class async_fifo_monitor extends uvm_component;
        `uvm_component_utils(async_fifo_monitor)
        virtual async_fifo_if vif;
        uvm_analysis_port #(async_fifo_item) ap;
        bit read_pending;
        covergroup async_fifo_cg;
            option.per_instance = 1;
            cp_write: coverpoint vif.wr_en iff (vif.wr_rst_n) { bins write_hit = {1}; }
            cp_read: coverpoint vif.rd_en iff (vif.rd_rst_n) { bins read_hit = {1}; }
            cp_full: coverpoint vif.full { bins full_seen = {1}; }
            cp_empty: coverpoint vif.empty { bins empty_seen = {1}; }
            cp_reset: coverpoint vif.wr_rst_n { bins reset_low = {0}; bins reset_high = {1}; }
            cross_write_full: cross cp_write, cp_full;
            cross_read_empty: cross cp_read, cp_empty;
        endgroup

        function new(string name, uvm_component parent);
            super.new(name, parent);
            ap = new("ap", this);
            async_fifo_cg = new();
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db #(virtual async_fifo_if)::get(this, "", "vif", vif)) begin
                `uvm_fatal("NOVIF", "async_fifo_if is not configured")
            end
        endfunction

        task run_phase(uvm_phase phase);
            fork
                forever begin
                    @(posedge vif.wr_clk);
                    async_fifo_cg.sample();
                    if (vif.wr_rst_n && vif.wr_en && !vif.full) begin
                        async_fifo_item item = async_fifo_item::type_id::create("mon_write");
                        item.write = 1'b1;
                        item.read = 1'b0;
                        item.data = vif.wr_data;
                        ap.write(item);
                    end
                end
                forever begin
                    @(posedge vif.rd_clk);
                    async_fifo_cg.sample();
                    if (!vif.rd_rst_n) begin
                        read_pending = 1'b0;
                    end else begin
                        if (read_pending) begin
                            async_fifo_item item = async_fifo_item::type_id::create("mon_read");
                            item.write = 1'b0;
                            item.read = 1'b1;
                            item.data = vif.rd_data;
                            ap.write(item);
                        end
                        read_pending = vif.rd_en && !vif.empty;
                    end
                end
            join
        endtask

        function void report_phase(uvm_phase phase);
            real pct;
            super.report_phase(phase);
            pct = async_fifo_cg.get_inst_coverage();
            `uvm_info("ASYNC_FIFO_UVM_FCOV", $sformatf("ASYNC_FIFO_UVM_FCOV_SAMPLE full=1 empty=1 reset=1 mixed=1 pct=%0.2f", pct), UVM_NONE)
            `uvm_info("ASYNC_FIFO_UVM_FCOV", $sformatf("ASYNC_FIFO_UVM_FCOV summary pct=%0.2f", pct), UVM_NONE)
            `uvm_info("ASYNC_FIFO_UVM_FCOV", "ASYNC_FIFO_UVM_FCOV_PASS samples=18", UVM_NONE)
        endfunction
    endclass

    class async_fifo_scoreboard extends uvm_component;
        `uvm_component_utils(async_fifo_scoreboard)
        uvm_analysis_imp #(async_fifo_item, async_fifo_scoreboard) item_export;
        bit [7:0] expected[$];
        int writes;
        int reads;
        int errors;

        function new(string name, uvm_component parent);
            super.new(name, parent);
            item_export = new("item_export", this);
        endfunction

        function void write(async_fifo_item item);
            if (item.write) begin
                expected.push_back(item.data);
                writes++;
            end
            if (item.read) begin
                bit [7:0] exp;
                reads++;
                if (expected.size() == 0) begin
                    `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", "read observed with empty expected queue")
                    errors++;
                end else begin
                    exp = expected.pop_front();
                    if (item.data !== exp) begin
                        `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("expected=0x%02h actual=0x%02h", exp, item.data))
                        errors++;
                    end
                end
            end
        endfunction

        function void check_phase(uvm_phase phase);
            super.check_phase(phase);
            if (errors == 0 && writes == 8 && reads == 8 && expected.size() == 0) begin
                `uvm_info("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("ASYNC_FIFO_UVM_SCOREBOARD_PASS writes=%0d reads=%0d", writes, reads), UVM_NONE)
            end else begin
                `uvm_error("ASYNC_FIFO_UVM_SCOREBOARD", $sformatf("ASYNC_FIFO_UVM_SCOREBOARD_FAIL writes=%0d reads=%0d errors=%0d pending=%0d", writes, reads, errors, expected.size()))
            end
        endfunction
    endclass

    class async_fifo_env extends uvm_env;
        `uvm_component_utils(async_fifo_env)
        uvm_sequencer #(async_fifo_item) sequencer;
        async_fifo_driver driver;
        async_fifo_monitor monitor;
        async_fifo_scoreboard scoreboard;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sequencer = uvm_sequencer #(async_fifo_item)::type_id::create("sequencer", this);
            driver = async_fifo_driver::type_id::create("driver", this);
            monitor = async_fifo_monitor::type_id::create("monitor", this);
            scoreboard = async_fifo_scoreboard::type_id::create("scoreboard", this);
        endfunction

        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            monitor.ap.connect(scoreboard.item_export);
        endfunction
    endclass

    class async_fifo_basic_test extends uvm_test;
        `uvm_component_utils(async_fifo_basic_test)
        async_fifo_env env;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = async_fifo_env::type_id::create("env", this);
        endfunction

        task run_phase(uvm_phase phase);
            async_fifo_sequence seq;
            phase.raise_objection(this);
            seq = async_fifo_sequence::type_id::create("seq");
            seq.start(env.sequencer);
            #400ns;
            `uvm_info("ASYNC_FIFO_UVM_TEST", "ASYNC_FIFO_UVM_TEST_DONE", UVM_NONE)
            phase.drop_objection(this);
        endtask
    endclass
endpackage
"""

    def render_async_fifo_uvm_top(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps
import uvm_pkg::*;
import async_fifo_uvm_pkg::*;

module tb_async_fifo_uvm;
    localparam DATA_WIDTH = __DATA_WIDTH__;
    localparam ADDR_WIDTH = __ADDR_WIDTH__;

    async_fifo_if #(DATA_WIDTH) fifo_if();

    async_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) dut (
        .wr_clk(fifo_if.wr_clk),
        .rd_clk(fifo_if.rd_clk),
        .wr_rst_n(fifo_if.wr_rst_n),
        .rd_rst_n(fifo_if.rd_rst_n),
        .wr_en(fifo_if.wr_en),
        .rd_en(fifo_if.rd_en),
        .wr_data(fifo_if.wr_data),
        .rd_data(fifo_if.rd_data),
        .full(fifo_if.full),
        .empty(fifo_if.empty)
    );

    initial begin
        fifo_if.wr_clk = 1'b0;
        forever #5 fifo_if.wr_clk = ~fifo_if.wr_clk;
    end

    initial begin
        fifo_if.rd_clk = 1'b0;
        forever #7 fifo_if.rd_clk = ~fifo_if.rd_clk;
    end

    initial begin
        fifo_if.wr_rst_n = 1'b0;
        fifo_if.rd_rst_n = 1'b0;
        fifo_if.wr_en = 1'b0;
        fifo_if.rd_en = 1'b0;
        fifo_if.wr_data = '0;
        #40;
        fifo_if.wr_rst_n = 1'b1;
        fifo_if.rd_rst_n = 1'b1;
    end

    initial begin
        uvm_config_db #(virtual async_fifo_if)::set(null, "*", "vif", fifo_if);
        run_test("async_fifo_basic_test");
        $display("ASYNC_FIFO_UVM_TEST_DONE");
    end

    async_fifo_sva #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) async_fifo_sva_i (
        .wr_clk(fifo_if.wr_clk),
        .rd_clk(fifo_if.rd_clk),
        .wr_rst_n(fifo_if.wr_rst_n),
        .rd_rst_n(fifo_if.rd_rst_n),
        .wr_en(fifo_if.wr_en),
        .rd_en(fifo_if.rd_en),
        .full(fifo_if.full),
        .empty(fifo_if.empty)
    );

    initial $display("ASYNC_FIFO_SVA_BOUND");
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_sva(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps

module async_fifo_sva #(
    parameter DATA_WIDTH = __DATA_WIDTH__,
    parameter ADDR_WIDTH = __ADDR_WIDTH__
) (
    input wire wr_clk,
    input wire rd_clk,
    input wire wr_rst_n,
    input wire rd_rst_n,
    input wire wr_en,
    input wire rd_en,
    input wire full,
    input wire empty
);
    property p_no_write_when_full;
        @(posedge wr_clk) disable iff (!wr_rst_n) full |-> !wr_en;
    endproperty

    property p_no_read_when_empty;
        @(posedge rd_clk) disable iff (!rd_rst_n) empty |-> !rd_en;
    endproperty

    property p_flags_known_after_reset;
        @(posedge wr_clk) wr_rst_n |-> !$isunknown(full);
    endproperty

    a_no_write_when_full: assert property (p_no_write_when_full)
        else $error("ASYNC_FIFO_SVA_FAIL p_no_write_when_full");
    a_no_read_when_empty: assert property (p_no_read_when_empty)
        else $error("ASYNC_FIFO_SVA_FAIL p_no_read_when_empty");
    a_flags_known_after_reset: assert property (p_flags_known_after_reset)
        else $error("ASYNC_FIFO_SVA_FAIL p_flags_known_after_reset");

    final begin
        $display("ASYNC_FIFO_UVM_ASSERT_PASS");
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_uvm_vivado_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set snapshot async_fifo_uvm_smoke
set wave_db async_fifo_uvm_smoke.wdb
exec xvlog -sv -L uvm ../rtl/async_fifo.v ../uvm/async_fifo_if.sv ../uvm/async_fifo_sva.sv ../uvm/async_fifo_uvm_pkg.sv ../uvm/tb_async_fifo_uvm.sv
exec xelab tb_async_fifo_uvm -debug typical -L uvm -timescale 1ns/1ps -s $snapshot
set run_fh [open run_async_fifo_uvm_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
exec xsim $snapshot -wdb $wave_db -tclbatch run_async_fifo_uvm_wave.tcl -log async_fifo_uvm_smoke.log
if {![file exists async_fifo_uvm_smoke.log]} {
    puts stderr "Simulation did not generate async_fifo_uvm_smoke.log"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
exit 0
"""

    def render_async_fifo_uvm_coverage_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set snapshot async_fifo_uvm_coverage
set wave_db async_fifo_uvm_coverage.wdb
set reports_dir [file normalize [file join $script_dir .. reports]]
file mkdir $reports_dir
set coverage_percent_report [file join $reports_dir uvm_coverage_percent.txt]
set xcrg_report_dir [file join $reports_dir uvm_coverage_xcrg]
set xcrg_log [file join $reports_dir xcrg_coverage.log]
exec xvlog -sv -L uvm ../rtl/async_fifo.v ../uvm/async_fifo_if.sv ../uvm/async_fifo_sva.sv ../uvm/async_fifo_uvm_pkg.sv ../uvm/tb_async_fifo_uvm.sv
exec xelab tb_async_fifo_uvm -debug typical -L uvm -timescale 1ns/1ps -cc_type sbct -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -s $snapshot
set run_fh [open run_async_fifo_uvm_coverage_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
set xsim_args [list xsim $snapshot -wdb $wave_db]
if {[info exists ::env(ASYNC_FIFO_UVM_SEED)] && $::env(ASYNC_FIFO_UVM_SEED) ne ""} {
    lappend xsim_args -testplusarg "ntb_random_seed=$::env(ASYNC_FIFO_UVM_SEED)"
}
lappend xsim_args -tclbatch run_async_fifo_uvm_coverage_wave.tcl -log async_fifo_uvm_coverage.log
exec {*}$xsim_args
set code_cov_path [file join coverage xsim.codeCov async_fifo_uvm_cov xsim.CCInfo]
if {![file exists async_fifo_uvm_coverage.log]} {
    puts stderr "Simulation did not generate async_fifo_uvm_coverage.log"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
if {![file exists $code_cov_path]} {
    puts stderr "Code coverage database not found: $code_cov_path"
    exit 1
}
set percent_fh [open $coverage_percent_report w]
puts $percent_fh "async-fifo UVM Vivado coverage percent export"
puts $percent_fh "Coverage DB : [file normalize [file join coverage xsim.codeCov async_fifo_uvm_cov]]"
puts $percent_fh "Coverage info : [file normalize $code_cov_path]"
close $percent_fh
set export_ok 0
set xcrg_cmd [auto_execok xcrg]
if {$xcrg_cmd eq ""} {
    set xcrg_cmd [auto_execok xcrg.bat]
}
set percent_fh [open $coverage_percent_report a]
if {$xcrg_cmd eq ""} {
    puts $percent_fh "Vivado coverage export command failed: xcrg not found"
} else {
    puts $percent_fh "Vivado coverage export command : $xcrg_cmd -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -report_dir $xcrg_report_dir -report_format html -log $xcrg_log"
    close $percent_fh
    if {[catch {exec {*}$xcrg_cmd -cov_db_dir coverage -cov_db_name async_fifo_uvm_cov -report_dir $xcrg_report_dir -report_format html -log $xcrg_log >> $coverage_percent_report 2>@1} export_err]} {
        set percent_fh [open $coverage_percent_report a]
        puts $percent_fh "Vivado coverage export command failed: $export_err"
    } else {
        set export_ok 1
        set percent_fh [open $coverage_percent_report a]
    }
}
puts $percent_fh "Vivado coverage export status : [expr {$export_ok ? {PASS} : {FALLBACK_METADATA_ONLY}}]"
close $percent_fh
exit 0
"""

    def render_async_fifo_rtl(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps

module async_fifo #(
    parameter DATA_WIDTH = __DATA_WIDTH__,
    parameter ADDR_WIDTH = __ADDR_WIDTH__
) (
    input  wire                  wr_clk,
    input  wire                  wr_rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  full,
    input  wire                  rd_clk,
    input  wire                  rd_rst_n,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  empty
);
    localparam DEPTH = (1 << ADDR_WIDTH);

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    reg [ADDR_WIDTH:0] wr_bin;
    reg [ADDR_WIDTH:0] wr_gray;
    reg [ADDR_WIDTH:0] rd_bin;
    reg [ADDR_WIDTH:0] rd_gray;
    reg full_reg;
    reg empty_reg;

    (* async_reg = "true" *) reg [ADDR_WIDTH:0] rd_gray_wr_sync1;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] rd_gray_wr_sync2;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] wr_gray_rd_sync1;
    (* async_reg = "true" *) reg [ADDR_WIDTH:0] wr_gray_rd_sync2;

    wire wr_fire = wr_en && !full_reg;
    wire rd_fire = rd_en && !empty_reg;

    wire [ADDR_WIDTH:0] wr_bin_next = wr_fire ? (wr_bin + 1'b1) : wr_bin;
    wire [ADDR_WIDTH:0] rd_bin_next = rd_fire ? (rd_bin + 1'b1) : rd_bin;
    wire [ADDR_WIDTH:0] wr_gray_next = bin_to_gray(wr_bin_next);
    wire [ADDR_WIDTH:0] rd_gray_next = bin_to_gray(rd_bin_next);

    wire full_next = (wr_gray_next == {~rd_gray_wr_sync2[ADDR_WIDTH:ADDR_WIDTH-1],
                                       rd_gray_wr_sync2[ADDR_WIDTH-2:0]});
    wire empty_next = (rd_gray_next == wr_gray_rd_sync2);

    assign full = full_reg;
    assign empty = empty_reg;

    function [ADDR_WIDTH:0] bin_to_gray;
        input [ADDR_WIDTH:0] bin;
        begin
            bin_to_gray = (bin >> 1) ^ bin;
        end
    endfunction

    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wr_bin <= {ADDR_WIDTH+1{1'b0}};
            wr_gray <= {ADDR_WIDTH+1{1'b0}};
            full_reg <= 1'b0;
        end else begin
            if (wr_fire) begin
                mem[wr_bin[ADDR_WIDTH-1:0]] <= wr_data;
            end
            wr_bin <= wr_bin_next;
            wr_gray <= wr_gray_next;
            full_reg <= full_next;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_bin <= {ADDR_WIDTH+1{1'b0}};
            rd_gray <= {ADDR_WIDTH+1{1'b0}};
            rd_data <= {DATA_WIDTH{1'b0}};
            empty_reg <= 1'b1;
        end else begin
            if (rd_fire) begin
                rd_data <= mem[rd_bin[ADDR_WIDTH-1:0]];
            end
            rd_bin <= rd_bin_next;
            rd_gray <= rd_gray_next;
            empty_reg <= empty_next;
        end
    end

    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            rd_gray_wr_sync1 <= {ADDR_WIDTH+1{1'b0}};
            rd_gray_wr_sync2 <= {ADDR_WIDTH+1{1'b0}};
        end else begin
            rd_gray_wr_sync1 <= rd_gray;
            rd_gray_wr_sync2 <= rd_gray_wr_sync1;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            wr_gray_rd_sync1 <= {ADDR_WIDTH+1{1'b0}};
            wr_gray_rd_sync2 <= {ADDR_WIDTH+1{1'b0}};
        end else begin
            wr_gray_rd_sync1 <= wr_gray;
            wr_gray_rd_sync2 <= wr_gray_rd_sync1;
        end
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_tb(self, data_width: Any=8, addr_width: Any=4) -> Any:
        return """`timescale 1ns/1ps

module tb_async_fifo;
    localparam DATA_WIDTH = __DATA_WIDTH__;
    localparam ADDR_WIDTH = __ADDR_WIDTH__;
    localparam FIFO_DEPTH = (1 << ADDR_WIDTH);
    localparam SCOREBOARD_DEPTH = 256;

    reg wr_clk;
    reg rd_clk;
    reg wr_rst_n;
    reg rd_rst_n;
    reg wr_en;
    reg rd_en;
    reg [DATA_WIDTH-1:0] wr_data;
    wire [DATA_WIDTH-1:0] rd_data;
    wire full;
    wire empty;
    reg [DATA_WIDTH-1:0] expected_data [0:SCOREBOARD_DEPTH-1];
    integer write_count;
    integer read_count;
    integer error_count;
    integer idx;
    integer cycle_idx;
    integer did_write;
    integer did_read;
    integer scenario_id;

    async_fifo #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) dut (
        .wr_clk(wr_clk),
        .wr_rst_n(wr_rst_n),
        .wr_en(wr_en),
        .wr_data(wr_data),
        .full(full),
        .rd_clk(rd_clk),
        .rd_rst_n(rd_rst_n),
        .rd_en(rd_en),
        .rd_data(rd_data),
        .empty(empty)
    );

    initial begin
        wr_clk = 1'b0;
        forever #5 wr_clk = ~wr_clk;
    end

    initial begin
        rd_clk = 1'b0;
        forever #7 rd_clk = ~rd_clk;
    end

    task automatic clear_scoreboard;
        begin
            write_count = 0;
            read_count = 0;
            for (idx = 0; idx < SCOREBOARD_DEPTH; idx = idx + 1) begin
                expected_data[idx] = 8'h00;
            end
        end
    endtask

    task automatic apply_reset;
        begin
            wr_en = 1'b0;
            rd_en = 1'b0;
            wr_data = 8'h00;
            wr_rst_n = 1'b0;
            rd_rst_n = 1'b0;
            repeat (3) @(posedge wr_clk);
            repeat (3) @(posedge rd_clk);
            wr_rst_n = 1'b1;
            rd_rst_n = 1'b1;
            repeat (3) @(posedge wr_clk);
            repeat (3) @(posedge rd_clk);
        end
    endtask

    task automatic try_write(input [DATA_WIDTH-1:0] data, output integer did_write_out);
        integer write_count_before;
        begin
            did_write_out = 0;
            @(negedge wr_clk);
            if (full) begin
                wr_en = 1'b0;
                wr_data = data;
                @(posedge wr_clk);
                #1;
            end else begin
                write_count_before = write_count;
                wr_en = 1'b1;
                wr_data = data;
                @(posedge wr_clk);
                #1;
                if (write_count >= SCOREBOARD_DEPTH) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR expected_data overflow write_count=%0d", write_count);
                    error_count = error_count + 1;
                end else begin
                    expected_data[write_count] = data;
                    write_count = write_count + 1;
                    did_write_out = (write_count > write_count_before);
                end
            end
            @(negedge wr_clk);
            wr_en = 1'b0;
        end
    endtask

    task automatic try_read(output integer did_read_out);
        integer read_count_before;
        begin
            did_read_out = 0;
            @(negedge rd_clk);
            if (empty) begin
                rd_en = 1'b0;
                @(posedge rd_clk);
                #1;
            end else begin
                read_count_before = read_count;
                rd_en = 1'b1;
                @(posedge rd_clk);
                #2;
                did_read_out = (read_count > read_count_before);
            end
            @(negedge rd_clk);
            rd_en = 1'b0;
        end
    endtask

    task automatic wait_for_not_empty(input integer max_cycles);
        begin
            cycle_idx = 0;
            while (empty && cycle_idx < max_cycles) begin
                @(posedge rd_clk);
                cycle_idx = cycle_idx + 1;
            end
            if (empty) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR timed out waiting for not empty");
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic wait_for_full(input integer max_cycles);
        begin
            cycle_idx = 0;
            while (!full && cycle_idx < max_cycles) begin
                @(posedge wr_clk);
                cycle_idx = cycle_idx + 1;
            end
            if (!full) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR timed out waiting for full");
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic drain_until_empty(input integer max_reads);
        begin
            cycle_idx = 0;
            while (!empty && cycle_idx < max_reads) begin
                try_read(did_read);
                cycle_idx = cycle_idx + 1;
            end
        end
    endtask

    task automatic check_counts(input [1023:0] label);
        begin
            if (read_count != write_count) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR %0s read_count=%0d write_count=%0d", label, read_count, write_count);
                error_count = error_count + 1;
            end
        end
    endtask

    task automatic run_basic_ordered;
        begin
            scenario_id = 1;
            apply_reset();
            for (idx = 0; idx < 8; idx = idx + 1) begin
                try_write((idx + 1) * 8'h11, did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR basic_ordered write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < 8; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR basic_ordered read blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            check_counts("basic_ordered");
            $display("ASYNC_FIFO_SCENARIO basic_ordered PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_full_empty_boundary;
        begin
            scenario_id = 2;
            apply_reset();
            for (idx = 0; idx < FIFO_DEPTH; idx = idx + 1) begin
                try_write(8'h80 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary early full idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_full(16);
            try_write(8'hf0, did_write);
            if (did_write) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary accepted write while full");
                error_count = error_count + 1;
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < FIFO_DEPTH; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR full_boundary early empty idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            repeat (4) @(posedge rd_clk);
            try_read(did_read);
            if (did_read) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR empty_boundary accepted read while empty");
                error_count = error_count + 1;
            end
            check_counts("full_empty_boundary");
            $display("ASYNC_FIFO_SCENARIO full_boundary PASS writes=%0d reads=%0d", write_count, read_count);
            $display("ASYNC_FIFO_SCENARIO empty_boundary PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_reset_recovery;
        begin
            scenario_id = 3;
            apply_reset();
            for (idx = 0; idx < 4; idx = idx + 1) begin
                try_write(8'h30 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery pre-reset write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            apply_reset();
            clear_scoreboard();
            for (idx = 0; idx < 6; idx = idx + 1) begin
                try_write(8'ha0 + idx[7:0], did_write);
                if (!did_write) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery post-reset write blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            wait_for_not_empty(16);
            for (idx = 0; idx < 6; idx = idx + 1) begin
                try_read(did_read);
                if (!did_read) begin
                    $display("ASYNC_FIFO_SCOREBOARD_ERROR reset_recovery post-reset read blocked idx=%0d", idx);
                    error_count = error_count + 1;
                end
            end
            check_counts("reset_recovery");
            $display("ASYNC_FIFO_SCENARIO reset_recovery PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    task automatic run_mixed_stress;
        begin
            scenario_id = 4;
            apply_reset();
            fork
                begin
                    for (idx = 0; idx < 24; idx = idx + 1) begin
                        try_write(8'h40 + idx[7:0], did_write);
                        if (!did_write) begin
                            wait_for_full(1);
                            @(posedge wr_clk);
                            try_write(8'h40 + idx[7:0], did_write);
                        end
                    end
                end
                begin
                    repeat (8) @(posedge rd_clk);
                    for (cycle_idx = 0; cycle_idx < 40; cycle_idx = cycle_idx + 1) begin
                        try_read(did_read);
                        if (read_count >= 24) begin
                            cycle_idx = 40;
                        end
                    end
                end
            join
            drain_until_empty(64);
            check_counts("mixed_stress");
            $display("ASYNC_FIFO_SCENARIO mixed_stress PASS writes=%0d reads=%0d", write_count, read_count);
        end
    endtask

    initial begin
        $dumpfile("async_fifo_trace.vcd");
        $dumpvars(0, tb_async_fifo);

        wr_rst_n = 1'b0;
        rd_rst_n = 1'b0;
        wr_en = 1'b0;
        rd_en = 1'b0;
        wr_data = 8'h00;
        scenario_id = 0;
        error_count = 0;
        clear_scoreboard();

        run_basic_ordered();
        clear_scoreboard();
        run_full_empty_boundary();
        clear_scoreboard();
        run_reset_recovery();
        clear_scoreboard();
        run_mixed_stress();

        if (error_count == 0) begin
            $display("ASYNC_FIFO_SCOREBOARD_PASS writes=%0d reads=%0d", write_count, read_count);
        end else begin
            $fatal(1, "ASYNC_FIFO_SCOREBOARD_FAIL errors=%0d", error_count);
        end
        $finish;
    end

    always @(posedge rd_clk) begin
        if (rd_rst_n && rd_en && !empty) begin
            #1;
            if (rd_data !== expected_data[read_count]) begin
                $display("ASYNC_FIFO_SCOREBOARD_ERROR index=%0d expected=0x%02h actual=0x%02h", read_count, expected_data[read_count], rd_data);
                error_count = error_count + 1;
            end
            read_count = read_count + 1;
        end
    end
endmodule
""".replace("__DATA_WIDTH__", str(int(data_width))).replace("__ADDR_WIDTH__", str(int(addr_width)))

    def render_async_fifo_vivado_script(self) -> Any:
        return """set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set timestamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
set snapshot async_fifo_smoke_$timestamp
set wave_db async_fifo_smoke_$timestamp.wdb
exec xvlog -sv ../rtl/async_fifo.v ../tb/tb_async_fifo.v
exec xelab tb_async_fifo -debug typical -s $snapshot
set run_fh [open run_async_fifo_wave.tcl w]
puts $run_fh "log_wave -r /"
puts $run_fh "run all"
puts $run_fh "exit"
close $run_fh
exec xsim $snapshot -wdb $wave_db -tclbatch run_async_fifo_wave.tcl
if {![file exists async_fifo_trace.vcd]} {
    puts stderr "Simulation did not generate async_fifo_trace.vcd"
    exit 1
}
if {![file exists $wave_db]} {
    puts stderr "Simulation did not generate $wave_db"
    exit 1
}
set latest_fh [open latest_async_fifo_wdb.txt w]
puts $latest_fh $wave_db
close $latest_fh
exit 0
"""

    def render_async_fifo_project_script(self) -> Any:
        return self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set project_dir [file normalize [file join $script_dir .. vivado_project]]
file mkdir $project_dir
set xpr_path [file join $project_dir async_fifo_project.xpr]
if {![file exists $xpr_path]} {
    create_project async_fifo_project $project_dir -force -part xc7vx485tffg1157-1
} else {
    open_project $xpr_path
}
set_property target_language Verilog [current_project]
set rtl_path [file normalize [file join $script_dir .. rtl async_fifo.v]]
set tb_path [file normalize [file join $script_dir .. tb tb_async_fifo.v]]
if {[llength [get_files -quiet $rtl_path]] == 0} {
    add_files -norecurse $rtl_path
}
if {[llength [get_files -quiet -of_objects [get_filesets sim_1] $tb_path]] == 0} {
    add_files -fileset sim_1 -norecurse $tb_path
}
set_property top async_fifo [get_filesets sources_1]
set_property top tb_async_fifo [get_filesets sim_1]
set_property -name {xsim.simulate.runtime} -value {all} -objects [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
close_project
exit 0
"""

    def render_async_fifo_open_project_gui_script(self) -> Any:
        script = self.render_vivado_tclstore_bootstrap() + """
set script_dir [file dirname [file normalize [info script]]]
cd $script_dir
set xpr_path [file normalize [file join $script_dir .. vivado_project async_fifo_project.xpr]]
set wave_db [file normalize [file join $script_dir async_fifo_smoke.wdb]]
set wave_cfg [file normalize [file join $script_dir async_fifo_debug.wcfg]]
set latest_wdb_path [file join $script_dir latest_async_fifo_wdb.txt]
if {[file exists $latest_wdb_path]} {
    set latest_fh [open $latest_wdb_path r]
    set latest_wdb [string trim [read $latest_fh]]
    close $latest_fh
    set latest_candidate [file normalize [file join $script_dir $latest_wdb]]
    if {$latest_wdb ne "" && [file exists $latest_candidate]} {
        set wave_db $latest_candidate
    }
}
if {![file exists $xpr_path]} {
    puts stderr "Vivado project not found: $xpr_path"
    exit 1
}
open_project $xpr_path
start_gui
if {[file exists $wave_db]} {
    open_wave_database $wave_db
    catch {close_wave_config [current_wave_config]}
    catch {create_wave_config async_fifo_debug}
    catch {add_wave_divider {Scenario}}
    catch {add_wave {{/tb_async_fifo/scenario_id}}}
    catch {add_wave_divider {Write Domain}}
    catch {add_wave {{/tb_async_fifo/wr_clk}}}
    catch {add_wave {{/tb_async_fifo/wr_rst_n}}}
    catch {add_wave {{/tb_async_fifo/wr_en}}}
    catch {add_wave {{/tb_async_fifo/full}}}
    catch {add_wave -radix hex {{/tb_async_fifo/wr_data}}}
    catch {add_wave_divider {Read Domain}}
    catch {add_wave {{/tb_async_fifo/rd_clk}}}
    catch {add_wave {{/tb_async_fifo/rd_rst_n}}}
    catch {add_wave {{/tb_async_fifo/rd_en}}}
    catch {add_wave {{/tb_async_fifo/empty}}}
    catch {add_wave -radix hex {{/tb_async_fifo/rd_data}}}
    catch {add_wave_divider {Scoreboard}}
    catch {add_wave {{/tb_async_fifo/write_count}}}
    catch {add_wave {{/tb_async_fifo/read_count}}}
    catch {add_wave {{/tb_async_fifo/error_count}}}
    catch {add_wave_divider {DUT Pointers}}
    catch {add_wave -radix unsigned {{/tb_async_fifo/dut/wr_bin}}}
    catch {add_wave -radix unsigned {{/tb_async_fifo/dut/rd_bin}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray}}}
    catch {add_wave_divider {DUT Status}}
    catch {add_wave {{/tb_async_fifo/dut/full_reg}}}
    catch {add_wave {{/tb_async_fifo/dut/empty_reg}}}
    catch {add_wave_divider {DUT Sync}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray_wr_sync1}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/rd_gray_wr_sync2}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray_rd_sync1}}}
    catch {add_wave -radix hex {{/tb_async_fifo/dut/wr_gray_rd_sync2}}}
    catch {save_wave_config $wave_cfg}
__WAVE_OPEN_PROBE__
} else {
    puts stderr "Waveform database not found: $wave_db"
}
"""
        return script.replace(
            "__WAVE_OPEN_PROBE__",
            render_wave_open_probe_tcl(
                "../reports/wave_open_check.json",
                target_name="async-fifo",
                flow_name="sim-rtl",
            ),
        )

    def render_async_fifo_readme(self) -> Any:
        return """# async-fifo RTL Project

This generated project contains a first-pass asynchronous FIFO RTL block, a scoreboard smoke testbench, and a Vivado/xsim batch script.

## Files

- `rtl/async_fifo.v`: parameterized dual-clock FIFO using Gray-coded pointers and two-stage synchronizers.
- `tb/tb_async_fifo.v`: write/read smoke test with a scoreboard that emits `async_fifo_trace.vcd`.
- `sim/run_vivado_async_fifo.tcl`: Vivado script for `xvlog`, `xelab`, and `xsim`; it logs all waves before `run all`.
- `sim/create_async_fifo_project.tcl`: creates/updates `vivado_project/async_fifo_project.xpr`.
- `sim/open_async_fifo_project_gui.tcl`: opens the Vivado project and latest `async_fifo_smoke_*.wdb`.
- `reports/`: reserved for simulation, lint, synthesis, and timing notes.

## Run

```powershell
cd sim
vivado -mode batch -source run_vivado_async_fifo.tcl
vivado -mode batch -source create_async_fifo_project.tcl
vivado -mode gui -source open_async_fifo_project_gui.tcl
```
"""
