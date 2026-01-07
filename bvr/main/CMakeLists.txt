idf_component_register(SRCS 
"main.c"
"LCD_Driver/ST7789.c"
"LCD_Driver/Vernon_ST7789T/Vernon_ST7789T.c"
                       PRIV_REQUIRES spi_flash driver esp_lcd esp_hid esp_timer
                       INCLUDE_DIRS
                              "./LCD_Driver/Vernon_ST7789T" 
                              "./LCD_Driver" 
                       EMBED_FILES "house.bmp"
                       )
