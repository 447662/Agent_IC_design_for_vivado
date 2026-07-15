package timer_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    class timer_item extends uvm_sequence_item;
        rand bit load;
        rand bit enable;
        rand bit [15:0] period;
        bit rst_n;
        bit expired;

        constraint useful_period { period inside {[0:7]}; }
        `uvm_object_utils_begin(timer_item)
            `uvm_field_int(load, UVM_DEFAULT)
            `uvm_field_int(enable, UVM_DEFAULT)
            `uvm_field_int(period, UVM_DEFAULT)
            `uvm_field_int(expired, UVM_DEFAULT | UVM_NOCOMPARE)
        `uvm_object_utils_end

        function new(string name = "timer_item");
            super.new(name);
        endfunction
    endclass

    class timer_sequence extends uvm_sequence #(timer_item);
        `uvm_object_utils(timer_sequence)
        function new(string name = "timer_sequence");
            super.new(name);
        endfunction

        task body();
            timer_item item;
            repeat (48) begin
                item = timer_item::type_id::create("item");
                start_item(item);
                assert(item.randomize() with {
                    load dist {1 := 1, 0 := 5};
                    enable dist {1 := 4, 0 := 1};
                });
                finish_item(item);
            end
        endtask
    endclass

    class timer_driver extends uvm_driver #(timer_item);
        `uvm_component_utils(timer_driver)
        virtual timer_if vif;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual timer_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "timer_if was not configured")
        endfunction

        task run_phase(uvm_phase phase);
            timer_item item;
            vif.drv_cb.load <= 1'b0;
            vif.drv_cb.enable <= 1'b0;
            vif.drv_cb.period <= '0;
            forever begin
                seq_item_port.get_next_item(item);
                @(vif.drv_cb);
                vif.drv_cb.load <= item.load;
                vif.drv_cb.enable <= item.enable;
                vif.drv_cb.period <= item.period;
                seq_item_port.item_done();
            end
        endtask
    endclass

    class timer_monitor extends uvm_component;
        `uvm_component_utils(timer_monitor)
        virtual timer_if vif;
        uvm_analysis_port #(timer_item) observed;
        covergroup controls;
            option.per_instance = 1;
            cp_load: coverpoint vif.mon_cb.load;
            cp_enable: coverpoint vif.mon_cb.enable;
            cp_period: coverpoint vif.mon_cb.period {
                bins zero = {0};
                bins short_period = {[1:3]};
                bins longer_period = {[4:7]};
            }
            cp_expired: coverpoint vif.mon_cb.expired;
            cross cp_load, cp_enable;
        endgroup

        function new(string name, uvm_component parent);
            super.new(name, parent);
            observed = new("observed", this);
            controls = new();
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(virtual timer_if)::get(this, "", "vif", vif))
                `uvm_fatal("NOVIF", "timer_if was not configured")
        endfunction

        task run_phase(uvm_phase phase);
            timer_item item;
            forever begin
                @(vif.mon_cb);
                item = timer_item::type_id::create("observed_item");
                item.rst_n = vif.mon_cb.rst_n;
                item.load = vif.mon_cb.load;
                item.enable = vif.mon_cb.enable;
                item.period = vif.mon_cb.period;
                item.expired = vif.mon_cb.expired;
                controls.sample();
                observed.write(item);
            end
        endtask
    endclass

    class timer_scoreboard extends uvm_subscriber #(timer_item);
        `uvm_component_utils(timer_scoreboard)
        bit [15:0] expected_remaining;
        bit expected_expired;
        int expiry_count;
        int error_count;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void write(timer_item item);
            if ($isunknown(item.expired)) begin
                error_count++;
                `uvm_error("TIMER_SB", "expired contains X/Z")
            end
            if (!item.rst_n) begin
                expected_remaining = '0;
                expected_expired = 1'b0;
            end else begin
                if (item.expired !== expected_expired) begin
                    error_count++;
                    `uvm_error("TIMER_SB", $sformatf("expired mismatch expected=%0d actual=%0d", expected_expired, item.expired))
                end
                if (item.expired)
                    expiry_count++;
                expected_expired = 1'b0;
                if (item.load) begin
                    expected_remaining = (item.period == '0) ? 16'd1 : item.period;
                end else if (item.enable) begin
                    if (expected_remaining <= 16'd1) begin
                        expected_expired = 1'b1;
                        expected_remaining = (item.period == '0) ? 16'd1 : item.period;
                    end else begin
                        expected_remaining--;
                    end
                end
            end
        endfunction

        function void check_phase(uvm_phase phase);
            super.check_phase(phase);
            if (expiry_count < 2) begin
                error_count++;
                `uvm_error("TIMER_SB", $sformatf("expected at least two expiries, observed %0d", expiry_count))
            end
        endfunction

        function void report_phase(uvm_phase phase);
            super.report_phase(phase);
            if (error_count == 0)
                $display("TIMER_SCOREBOARD_PASS expiries=%0d", expiry_count);
            else
                $display("TEST_FAILED TIMER_SCOREBOARD errors=%0d", error_count);
        endfunction
    endclass

    class timer_env extends uvm_env;
        `uvm_component_utils(timer_env)
        uvm_sequencer #(timer_item) sequencer;
        timer_driver driver;
        timer_monitor monitor;
        timer_scoreboard scoreboard;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            sequencer = uvm_sequencer#(timer_item)::type_id::create("sequencer", this);
            driver = timer_driver::type_id::create("driver", this);
            monitor = timer_monitor::type_id::create("monitor", this);
            scoreboard = timer_scoreboard::type_id::create("scoreboard", this);
        endfunction

        function void connect_phase(uvm_phase phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            monitor.observed.connect(scoreboard.analysis_export);
        endfunction
    endclass

    class timer_test extends uvm_test;
        `uvm_component_utils(timer_test)
        timer_env env;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            env = timer_env::type_id::create("env", this);
        endfunction

        task run_phase(uvm_phase phase);
            timer_sequence seq;
            phase.raise_objection(this);
            seq = timer_sequence::type_id::create("sequence");
            seq.start(env.sequencer);
            repeat (12) @(env.monitor.vif.mon_cb);
            phase.drop_objection(this);
        endtask
    endclass
endpackage
