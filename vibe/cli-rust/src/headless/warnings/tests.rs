//! Profile diagnostics reach the warning output while silent runs stay silent.

use crate::cli::OutputFormat;
use crate::run_export::RunWarning;

#[test]
fn sourced_warnings_reach_each_non_silent_output_mode() {
    let warnings = [RunWarning {
        source: Some(".vibe/agents/reviewer.toml".into()),
        message: "instructions: String should have at most 65536 characters".into(),
    }];
    for format in [
        OutputFormat::Text,
        OutputFormat::Json,
        OutputFormat::Streaming,
    ] {
        let mut output = Vec::new();
        super::write(&format, &warnings, &mut output).unwrap();
        assert_eq!(
            String::from_utf8(output).unwrap(),
            "Warning: .vibe/agents/reviewer.toml: instructions: String should have at most 65536 characters\n"
        );
    }
}

#[test]
fn silent_runs_emit_no_configuration_warnings() {
    let warnings = [RunWarning {
        source: Some(".vibe/agents/reviewer.toml".into()),
        message: "instructions are too long".into(),
    }];
    let mut output = Vec::new();
    super::write(&OutputFormat::Silent, &warnings, &mut output).unwrap();
    assert!(output.is_empty());
}

#[test]
fn unsourced_run_warnings_are_not_duplicated() {
    let warnings = [
        RunWarning {
            source: None,
            message: "run warning".into(),
        },
        RunWarning {
            source: Some(String::new()),
            message: "process warning".into(),
        },
    ];
    let mut output = Vec::new();
    super::write(&OutputFormat::Text, &warnings, &mut output).unwrap();
    assert!(output.is_empty());
}
