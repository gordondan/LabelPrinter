#!/usr/bin/wish

# Label Printer GUI - TCL/Tk wrapper for date-printer.py
# Provides a tabbed interface for organizing and executing label templates

package require Tk

# --- GLOBAL VARIABLES ---
set templates_dir "label-images"
set global_copy_count 1
set current_variables {}
set current_template_file ""
set date_printer_options {}

# --- UTILITY FUNCTIONS ---

proc create_directory_if_not_exists {dir_path} {
    if {![file exists $dir_path]} {
        file mkdir $dir_path
        puts "Created directory: $dir_path"
    }
}

proc get_categories {} {
    global templates_dir
    set categories {}
    
    if {[file exists $templates_dir] && [file isdirectory $templates_dir]} {
        foreach item [glob -nocomplain -type d [file join $templates_dir *]] {
            lappend categories [file tail $item]
        }
    }
    
    return [lsort $categories]
}

proc get_templates {category} {
    global templates_dir
    set templates {}
    set category_path [file join $templates_dir $category]
    
    if {[file exists $category_path] && [file isdirectory $category_path]} {
        foreach template_file [glob -nocomplain [file join $category_path "*.template"]] {
            set template_name [file rootname [file tail $template_file]]
            lappend templates [list $template_name $template_file]
        }
    }
    
    return [lsort $templates]
}

proc read_template_file {template_file} {
    if {![file exists $template_file]} {
        return ""
    }
    
    set fp [open $template_file r]
    set content [read $fp]
    close $fp
    
    return [string trim $content]
}

proc write_template_file {template_file content} {
    set fp [open $template_file w]
    puts $fp $content
    close $fp
}

proc extract_variables {template_content} {
    set variables {}
    set pattern {\{\{([^}]+)\}\}}
    
    while {[regexp -indices $pattern $template_content match var_indices]} {
        set var_name [string range $template_content [lindex $var_indices 0] [lindex $var_indices 1]]
        if {[lsearch -exact $variables $var_name] == -1} {
            lappend variables $var_name
        }
        set start_pos [expr {[lindex $match 1] + 1}]
        set template_content [string range $template_content $start_pos end]
    }
    
    return $variables
}

proc extract_defaults {template_content} {
    set defaults {}
    foreach line [split $template_content "\n"] {
        if {[regexp {^#\s*DEFAULT:\s*([^=]+)=(.*)$} $line match var_name var_value]} {
            set var_name [string trim $var_name]
            set var_value [string trim $var_value]
            dict set defaults $var_name $var_value
        }
    }
    return $defaults
}

proc substitute_variables {template_content variable_values} {
    set result $template_content
    
    foreach {var_name var_value} $variable_values {
        set pattern "\\{\\{$var_name\\}\\}"
        regsub -all $pattern $result $var_value result
    }
    
    return $result
}

proc get_copy_count_from_template {template_content} {
    global global_copy_count
    
    # Look for -c or --count in template
    if {[regexp {(?:^|\s)(?:-c|--count)\s+(\d+)} $template_content match count]} {
        return $count
    }
    
    return $global_copy_count
}

proc update_status {message} {
    .status_label configure -text $message
    update
}

# --- TEMPLATE EXECUTION ---

proc execute_template {template_file variable_values} {
    global global_copy_count
    
    update_status "Loading template..."
    
    set template_content [read_template_file $template_file]
    if {$template_content eq ""} {
        tk_messageBox -type ok -icon error -title "Error" -message "Could not read template file: $template_file"
        update_status "Ready"
        return
    }
    
    # Substitute variables
    set final_command [substitute_variables $template_content $variable_values]
    
    # Get copy count (template overrides global setting)
    set copy_count [get_copy_count_from_template $final_command]
    
    # If no -c in template, add global setting
    if {![regexp {(?:^|\s)(?:-c|--count)\s+\d+} $final_command]} {
        set final_command "$final_command -c $copy_count"
    }
    
    # Execute the command
    update_status "Printing label..."
    set command "python date-printer.py $final_command"
    
    puts "Executing: $command"
    
    if {[catch {exec {*}[split $command]} result]} {
        tk_messageBox -type ok -icon error -title "Print Error" -message "Failed to print label:\n$result"
        update_status "Print failed"
    } else {
        update_status "Label printed successfully"
        puts "Command output: $result"
        
        # Clear status after 3 seconds
        after 3000 {update_status "Ready"}
    }
}

# --- TEMPLATE CREATION DIALOG ---

proc get_date_printer_options {} {
    global date_printer_options
    
    if {[llength $date_printer_options] == 0} {
        # Parse help output to get available options
        if {[catch {exec python date-printer.py --help} help_output]} {
            return {}
        }
        
        # Extract options from help text
        set options {}
        foreach line [split $help_output "\n"] {
            if {[regexp {^\s*(-[a-zA-Z],?\s*)?--([a-zA-Z-]+)} $line match short_opt long_opt]} {
                set option_info [list $long_opt $short_opt $line]
                lappend options $option_info
            }
        }
        
        set date_printer_options $options
    }
    
    return $date_printer_options
}

proc create_template_dialog {category} {
    set dialog .template_dialog
    
    if {[winfo exists $dialog]} {
        destroy $dialog
    }
    
    toplevel $dialog
    wm title $dialog "Create New Template"
    wm geometry $dialog "600x500"
    wm transient $dialog .
    wm grab $dialog
    
    # Template name
    frame $dialog.name_frame
    label $dialog.name_frame.label -text "Template Name:"
    entry $dialog.name_frame.entry -width 30
    pack $dialog.name_frame.label -side left
    pack $dialog.name_frame.entry -side left -padx 10
    pack $dialog.name_frame -pady 10 -anchor w
    
    # Options frame with scrollbar
    frame $dialog.options_frame
    label $dialog.options_frame.label -text "Available Options:"
    pack $dialog.options_frame.label -anchor w
    
    frame $dialog.options_frame.scroll_frame
    scrollbar $dialog.options_frame.scroll_frame.scrollbar -command "$dialog.options_frame.scroll_frame.listbox yview"
    listbox $dialog.options_frame.scroll_frame.listbox -yscrollcommand "$dialog.options_frame.scroll_frame.scrollbar set" -height 15 -selectmode multiple
    pack $dialog.options_frame.scroll_frame.scrollbar -side right -fill y
    pack $dialog.options_frame.scroll_frame.listbox -side left -fill both -expand true
    pack $dialog.options_frame.scroll_frame -fill both -expand true
    pack $dialog.options_frame -fill both -expand true -pady 10
    
    # Populate options
    set options [get_date_printer_options]
    foreach option $options {
        set long_opt [lindex $option 0]
        set description [lindex $option 2]
        $dialog.options_frame.scroll_frame.listbox insert end "$long_opt - $description"
    }
    
    # Value entry frame
    frame $dialog.value_frame
    label $dialog.value_frame.label -text "Option Value (if needed):"
    entry $dialog.value_frame.entry -width 40
    pack $dialog.value_frame.label -side left
    pack $dialog.value_frame.entry -side left -padx 10
    pack $dialog.value_frame -pady 10 -anchor w
    
    # Preview frame
    frame $dialog.preview_frame
    label $dialog.preview_frame.label -text "Command Preview:"
    text $dialog.preview_frame.text -height 4 -width 60 -wrap word
    pack $dialog.preview_frame.label -anchor w
    pack $dialog.preview_frame.text -fill x
    pack $dialog.preview_frame -pady 10 -fill x
    
    # Buttons
    frame $dialog.buttons
    button $dialog.buttons.ok -text "Create Template" -command "create_template_ok $dialog $category"
    button $dialog.buttons.cancel -text "Cancel" -command "destroy $dialog"
    pack $dialog.buttons.cancel -side right -padx 5
    pack $dialog.buttons.ok -side right -padx 5
    pack $dialog.buttons -pady 10
    
    # Bind selection event to update preview
    bind $dialog.options_frame.scroll_frame.listbox <<ListboxSelect>> "update_template_preview $dialog"
    bind $dialog.value_frame.entry <KeyRelease> "update_template_preview $dialog"
}

proc update_template_preview {dialog} {
    set preview_text [$dialog.preview_frame.text get 1.0 end-1c]
    set selected_indices [$dialog.options_frame.scroll_frame.listbox curselection]
    set value [$dialog.value_frame.entry get]
    
    set command_parts {}
    
    foreach idx $selected_indices {
        set option_text [$dialog.options_frame.scroll_frame.listbox get $idx]
        if {[regexp {^([a-zA-Z-]+)} $option_text match option_name]} {
            if {$value ne ""} {
                lappend command_parts "--$option_name \"$value\""
            } else {
                lappend command_parts "--$option_name"
            }
        }
    }
    
    $dialog.preview_frame.text delete 1.0 end
    $dialog.preview_frame.text insert 1.0 [join $command_parts " "]
}

proc create_template_ok {dialog category} {
    global templates_dir
    
    set template_name [$dialog.name_frame.entry get]
    if {$template_name eq ""} {
        tk_messageBox -type ok -icon error -title "Error" -message "Please enter a template name"
        return
    }
    
    set command [$dialog.preview_frame.text get 1.0 end-1c]
    if {$command eq ""} {
        tk_messageBox -type ok -icon error -title "Error" -message "Please select at least one option"
        return
    }
    
    # Create category directory if it doesn't exist
    set category_path [file join $templates_dir $category]
    create_directory_if_not_exists $category_path
    
    # Write template file
    set template_file [file join $category_path "$template_name.template"]
    
    if {[file exists $template_file]} {
        set answer [tk_messageBox -type yesno -icon question -title "Template Exists" -message "Template '$template_name' already exists. Overwrite?"]
        if {$answer ne "yes"} {
            return
        }
    }
    
    write_template_file $template_file $command
    
    destroy $dialog
    refresh_current_tab
    update_status "Template '$template_name' created successfully"
}

# --- VARIABLE INPUT FORMS ---

proc create_variable_form {parent template_file} {
    global current_variables current_template_file
    
    set current_template_file $template_file
    set template_content [read_template_file $template_file]
    set variables [extract_variables $template_content]
    set defaults [extract_defaults $template_content]
    
    # Clear existing variable widgets
    foreach child [winfo children $parent.var_frame] {
        destroy $child
    }
    
    if {[llength $variables] == 0} {
        set current_variables {}
        return
    }
    
    set current_variables {}
    
    # Create input widgets for each variable
    set row 0
    foreach var_name $variables {
        set frame_name $parent.var_frame.var_$row
        frame $frame_name
        
        label $frame_name.label -text "$var_name:" -width 15 -anchor w
        entry $frame_name.entry -width 25
        
        # Set default value if available
        if {[dict exists $defaults $var_name]} {
            $frame_name.entry insert 0 [dict get $defaults $var_name]
        }
        
        # Save as default button
        button $frame_name.save_btn -text "Save as default" -command "save_variable_default $var_name $frame_name.entry"
        update_default_button_state $frame_name.save_btn $var_name $frame_name.entry $defaults
        
        # Bind entry change to update button state
        bind $frame_name.entry <KeyRelease> "update_default_button_state $frame_name.save_btn $var_name $frame_name.entry [list $defaults]"
        
        pack $frame_name.label -side left -padx 5
        pack $frame_name.entry -side left -padx 5
        pack $frame_name.save_btn -side left -padx 5
        pack $frame_name -pady 2 -anchor w
        
        lappend current_variables [list $var_name $frame_name.entry]
        incr row
    }
}

proc update_default_button_state {button var_name entry defaults} {
    set current_value [$entry get]
    set default_value ""
    
    if {[dict exists $defaults $var_name]} {
        set default_value [dict get $defaults $var_name]
    }
    
    if {$current_value eq $default_value} {
        $button configure -state disabled
    } else {
        $button configure -state normal
    }
}

proc save_variable_default {var_name entry} {
    global current_template_file
    
    set value [$entry get]
    set template_content [read_template_file $current_template_file]
    
    # Remove existing default for this variable
    set new_lines {}
    foreach line [split $template_content "\n"] {
        if {![regexp "^#\\s*DEFAULT:\\s*$var_name\\s*=" $line]} {
            lappend new_lines $line
        }
    }
    
    # Add new default
    lappend new_lines "# DEFAULT: $var_name=$value"
    
    set new_content [join $new_lines "\n"]
    write_template_file $current_template_file $new_content
    
    update_status "Default value saved for $var_name"
    
    # Refresh the form to update button states
    create_variable_form [winfo parent [winfo parent $entry]] $current_template_file
}

proc get_variable_values {} {
    global current_variables
    
    set values {}
    foreach var_info $current_variables {
        set var_name [lindex $var_info 0]
        set entry_widget [lindex $var_info 1]
        set var_value [$entry_widget get]
        lappend values $var_name $var_value
    }
    
    return $values
}

# --- TAB MANAGEMENT ---

proc create_category_tab {notebook category} {
    set tab_frame $notebook.tab_$category
    
    if {[winfo exists $tab_frame]} {
        destroy $tab_frame
    }
    
    frame $tab_frame
    $notebook add $tab_frame -text $category
    
    # Create main content frame
    frame $tab_frame.content
    pack $tab_frame.content -fill both -expand true -padx 10 -pady 10
    
    # Template buttons frame
    frame $tab_frame.content.templates
    label $tab_frame.content.templates.label -text "Templates:" -font {-weight bold}
    pack $tab_frame.content.templates.label -anchor w
    
    frame $tab_frame.content.templates.buttons
    pack $tab_frame.content.templates.buttons -fill x -pady 5
    
    # Add New Template button
    button $tab_frame.content.templates.new_btn -text "+ New Template" -command "create_template_dialog $category" -bg lightgreen
    pack $tab_frame.content.templates.new_btn -side left -padx 5
    
    pack $tab_frame.content.templates -fill x -pady 10
    
    # Variable input frame
    frame $tab_frame.content.var_frame
    pack $tab_frame.content.var_frame -fill x -pady 10
    
    # Print button
    frame $tab_frame.content.print_frame
    button $tab_frame.content.print_frame.print_btn -text "Print Label" -command "print_current_template" -bg lightblue -state disabled
    pack $tab_frame.content.print_frame.print_btn -side right
    pack $tab_frame.content.print_frame -fill x -pady 10
    
    # Load templates for this category
    refresh_category_templates $tab_frame $category
    
    return $tab_frame
}

proc refresh_category_templates {tab_frame category} {
    set templates [get_templates $category]
    
    # Clear existing template buttons
    foreach child [winfo children $tab_frame.content.templates.buttons] {
        if {[winfo class $child] eq "Button" && [$child cget -text] ne "+ New Template"} {
            destroy $child
        }
    }
    
    # Create template buttons
    foreach template $templates {
        set template_name [lindex $template 0]
        set template_file [lindex $template 1]
        
        button $tab_frame.content.templates.buttons.btn_$template_name \
            -text $template_name \
            -command "select_template {$template_file} $tab_frame" \
            -bg lightyellow
        
        pack $tab_frame.content.templates.buttons.btn_$template_name -side left -padx 2
    }
}

proc select_template {template_file tab_frame} {
    global current_template_file
    
    set current_template_file $template_file
    create_variable_form $tab_frame.content $template_file
    
    # Enable print button
    $tab_frame.content.print_frame.print_btn configure -state normal
    
    set template_name [file rootname [file tail $template_file]]
    update_status "Selected template: $template_name"
}

proc print_current_template {} {
    global current_template_file
    
    if {$current_template_file eq ""} {
        tk_messageBox -type ok -icon error -title "Error" -message "Please select a template first"
        return
    }
    
    set variable_values [get_variable_values]
    execute_template $current_template_file $variable_values
}

proc refresh_current_tab {} {
    set current_tab [.main.notebook select]
    if {$current_tab ne ""} {
        set tab_name [.main.notebook tab $current_tab -text]
        refresh_category_templates $current_tab $tab_name
    }
}

# --- MAIN GUI SETUP ---

proc create_main_window {} {
    global global_copy_count templates_dir
    
    wm title . "Label Printer GUI"
    wm geometry . "800x600"
    
    # Create main frame
    frame .main
    pack .main -fill both -expand true -padx 10 -pady 10
    
    # Global settings frame
    frame .main.settings
    label .main.settings.label -text "Global Copy Count:" -font {-weight bold}
    spinbox .main.settings.count -from 1 -to 99 -width 5 -textvariable global_copy_count
    pack .main.settings.label -side left
    pack .main.settings.count -side left -padx 10
    pack .main.settings -anchor w -pady 5
    
    # Create notebook for tabs
    ttk::notebook .main.notebook
    pack .main.notebook -fill both -expand true -pady 10
    
    # Status bar
    label .status_label -text "Ready" -relief sunken -anchor w
    pack .status_label -side bottom -fill x
    
    # Create initial directory structure
    create_directory_if_not_exists $templates_dir
    create_directory_if_not_exists [file join $templates_dir "family"]
    create_directory_if_not_exists [file join $templates_dir "office"]
    create_directory_if_not_exists [file join $templates_dir "personal"]
    
    refresh_tabs
}

proc refresh_tabs {} {
    set categories [get_categories]
    
    # Clear existing tabs
    foreach tab [.main.notebook tabs] {
        .main.notebook forget $tab
    }
    
    # Create tabs for each category
    if {[llength $categories] == 0} {
        # Create default categories if none exist
        set categories {"family" "office" "personal"}
    }
    
    foreach category $categories {
        create_category_tab .main.notebook $category
    }
}

# --- EXAMPLE TEMPLATES CREATION ---

proc create_example_templates {} {
    global templates_dir
    
    # Family templates
    set family_dir [file join $templates_dir "family"]
    create_directory_if_not_exists $family_dir
    
    set family_members {"Dan" "Lexie" "Tyrell" "Natalyn" "David" "Jacob" "Isabella" "Caleb" "Julia"}
    
    foreach member $family_members {
        set template_file [file join $family_dir "$member.template"]
        if {![file exists $template_file]} {
            set content "--message \"$member\" --font-size 24"
            write_template_file $template_file $content
        }
    }
    
    # Example template with variables
    set birthday_template [file join $family_dir "birthday.template"]
    if {![file exists $birthday_template]} {
        set content "--message \"{{name}}\" --border-message \"{{occasion}}\" --font-size 20\n# DEFAULT: occasion=Birthday"
        write_template_file $birthday_template $content
    }
    
    puts "Created example templates"
}

# --- MAIN EXECUTION ---

proc main {} {
    create_example_templates
    create_main_window
    update_status "Label Printer GUI loaded - Select a template to begin"
}

# Start the application
main