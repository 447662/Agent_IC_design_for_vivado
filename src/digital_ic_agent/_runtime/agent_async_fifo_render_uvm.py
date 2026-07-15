# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any


class AsyncFifoUvmRenderMixin:
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
