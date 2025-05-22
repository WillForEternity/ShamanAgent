use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }

      // Get the main window
      let main_window = app.get_webview_window("main").unwrap(); // "main" is the default label
      
      // Set the window to be visible on all workspaces (macOS specific behavior)
      #[cfg(target_os = "macos")]
      {
        main_window.set_visible_on_all_workspaces(true).unwrap_or_else(|e| {
          eprintln!("Failed to set window visible on all workspaces: {}", e);
        });
      }

      // Prevent the window from being captured in screenshots
      main_window.set_content_protected(true).unwrap_or_else(|e| {
        eprintln!("Failed to set content protection: {}", e);
      });

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
