use tauri::{GlobalShortcutManager, Manager};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      let app_handle = app.handle().clone();
      let mut shortcut_manager = app_handle.global_shortcut_manager();

      shortcut_manager.register("CmdOrCtrl+Shift+S", move || {
        println!("Global shortcut CmdOrCtrl+Shift+S triggered");
        if let Err(e) = app_handle.emit_all("trigger_screen_analysis", ()) {
            eprintln!("Failed to emit trigger_screen_analysis event: {}", e);
        }
      })?;

      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
