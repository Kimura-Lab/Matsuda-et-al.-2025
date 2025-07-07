# ========== 0. Load Required Packages ==========
#install.packages(c("readr", "dplyr", "tidyr", "car", "ggplot2", "ggpubr", "rstatix", "officer", "flextable", "NSM3"))

library(readr)
library(dplyr)
library(tidyr)
library(car)
library(ggplot2)
library(ggpubr)
library(rstatix)
library(officer)
library(flextable)

# ========== 1. Define Batch Processing for CSV Files ==========
process_csv_file <- function(file_path) {
  file_basename <- tools::file_path_sans_ext(basename(file_path))
  df <- read_csv(file_path)
  
  # Assume column 1 is ID (e.g., "mouse"), rest are organs
  organ_cols <- setdiff(names(df), "mouse")
  if (!"mouse" %in% names(df)) df$mouse <- "sample"
  
  df_long <- df %>%
    pivot_longer(cols = all_of(organ_cols),
                 names_to = "organ", values_to = "value") %>%
    drop_na()
  
  # --- Tests ---
  shapiro_res <- df_long %>%
    group_by(organ) %>%
    summarise(p_value = shapiro.test(value)$p.value)
  
  levene_result_df <- as.data.frame(leveneTest(value ~ organ, data = df_long))
  
  anova_model <- aov(value ~ organ, data = df_long)
  tukey_df <- as.data.frame(TukeyHSD(anova_model)$organ) %>%
    mutate(comparison = rownames(.)) %>%
    rename(p_adj = `p adj`) %>%
    mutate(p_label = case_when(
      p_adj < 0.001 ~ "(***)",
      p_adj < 0.01 ~ "(**)",
      p_adj < 0.05 ~ "(*)",
      TRUE ~ "(ns)"
    )) %>%
    separate(comparison, into = c("group1", "group2"), sep = "-")
  
  kruskal_df <- as.data.frame(kruskal_test(df_long, value ~ organ))
  
  dunn_holm_df <- df_long %>%
    dunn_test(value ~ organ, p.adjust.method = "holm") %>%
    mutate(p_label = case_when(
      p.adj < 0.001 ~ "(***)",
      p.adj < 0.01 ~ "(**)",
      p.adj < 0.05 ~ "(*)",
      TRUE ~ "(ns)"
    )) %>%
    rename(p_adj = p.adj)
  
  # --- Export Word File ---
  doc <- read_docx()
  add_section <- function(doc, title, df) {
    if (!is.null(df) && nrow(df) > 0 && ncol(df) > 0) {
      doc <- doc %>%
        body_add_par(title, style = "heading 1") %>%
        body_add_flextable(regulartable(df))
    } else {
      doc <- doc %>% body_add_par(paste(title, "(No results)"), style = "heading 1")
    }
    return(doc)
  }
  
  doc <- doc %>%
    add_section("Shapiro-Wilk Test", shapiro_res) %>%
    add_section("Levene’s Test", levene_result_df) %>%
    add_section("One-way ANOVA", as.data.frame(summary(anova_model)[[1]])) %>%
    add_section("Tukey HSD Post-hoc", tukey_df) %>%
    add_section("Kruskal-Wallis Test", kruskal_df) %>%
    add_section("Dunn-Holm Post-hoc", dunn_holm_df) 
  
  doc_path <- file.path(dirname(file_path), paste0(file_basename, "_tests.docx"))
  print(doc, target = doc_path)
  
  # --- Plot Function ---
  plot_with_significance <- function(df, test_name, file_suffix) {
    sig_df <- df %>% filter(p_adj < 0.05)
    max_y <- max(df_long$value)
    step <- 0.1 * max_y
    sig_df$y.position <- max_y + step * seq_len(nrow(sig_df))
    
    p <- ggplot(df_long, aes(x = organ, y = value)) +
      geom_boxplot(fill = "skyblue", outlier.shape = NA) +
      geom_jitter(width = 0.15, alpha = 0.5) +
      theme_bw(base_size = 14) +
      theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
      labs(title = paste0("Post-hoc: ", test_name), x = "Organ", y = "Value")
    
    if (nrow(sig_df) > 0) {
      p <- p + stat_pvalue_manual(
        sig_df,
        label = "p_label",
        xmin = "group1", xmax = "group2",
        y.position = "y.position",
        tip.length = 0.01
      )
    }
    
    file <- file.path(dirname(file_path), paste0(file_basename, "_boxplot_", file_suffix, ".png"))
    ggsave(file, plot = p, width = 8, height = 5)
  }
  
  plot_with_significance(tukey_df, "Tukey HSD", "tukey")
  plot_with_significance(dunn_holm_df, "Dunn-Holm", "dunn")
}

# ========== 2. Run Batch ==========
csv_files <- list.files(path = "~Yourpath/", pattern = "\\.csv$", full.names = TRUE)

for (file in csv_files) {
  cat("Processing:", file, "\n")
  try(process_csv_file(file), silent = TRUE)
}
