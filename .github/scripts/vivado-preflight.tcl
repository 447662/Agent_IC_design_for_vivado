puts "VIVADO_PREFLIGHT_VERSION [version -short]"

if {[catch {
    create_project -in_memory vivado_preflight -part xc7a35tcpg236-1
} message]} {
    puts stderr "VIVADO_PREFLIGHT_BLOCKED $message"
    exit 2
}

puts "VIVADO_PREFLIGHT_PASS"
close_project
exit 0
