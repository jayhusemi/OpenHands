import { Input, useDisclosure } from "@nextui-org/react";
import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { FaEye, FaEyeSlash } from "react-icons/fa";
import { useSelector } from "react-redux";
import { AvailableLanguages } from "../../../i18n";
import { I18nKey } from "../../../i18n/declaration";
import { RootState } from "../../../store";
import AgentTaskState from "../../../types/AgentTaskState";
import { AutocompleteCombobox } from "./AutocompleteCombobox";

interface SettingsFormProps {
  settings: Partial<Settings>;
  models: string[];
  apiKey: string;
  agents: string[];

  onModelChange: (model: string) => void;
  onAPIKeyChange: (apiKey: string) => void;
  onAgentChange: (agent: string) => void;
  onLanguageChange: (language: string) => void;
}

function SettingsForm({
  settings,
  models,
  apiKey,
  agents,
  onModelChange,
  onAPIKeyChange,
  onAgentChange,
  onLanguageChange,
}: SettingsFormProps) {
  const { t } = useTranslation();
  const { curTaskState } = useSelector((state: RootState) => state.agent);
  const [disabled, setDisabled] = React.useState<boolean>(false);
  const { isOpen: isVisible, onOpenChange: onVisibleChange } = useDisclosure();

  useEffect(() => {
    if (
      curTaskState === AgentTaskState.RUNNING ||
      curTaskState === AgentTaskState.PAUSED
    ) {
      setDisabled(true);
    } else {
      setDisabled(false);
    }
  }, [curTaskState, setDisabled]);

  return (
    <>
      <AutocompleteCombobox
        ariaLabel="model"
        items={models.map((model) => ({ value: model, label: model }))}
        defaultKey={settings.LLM_MODEL || models[0]}
        onChange={(e) => {
          const key = localStorage.getItem(
            `API_KEY_${settings.LLM_MODEL || models[0]}`,
          );
          onAPIKeyChange(key || "");
          onModelChange(e);
        }}
        tooltip={t(I18nKey.SETTINGS$MODEL_TOOLTIP)}
        allowCustomValue // user can type in a custom LLM model that is not in the list
        disabled={disabled}
      />
      <Input
        label="API Key"
        placeholder="Enter your API Key."
        type={isVisible ? "text" : "password"}
        value={apiKey}
        onChange={(e) => {
          localStorage.setItem(
            `API_KEY_${settings.LLM_MODEL || models[0]}`,
            e.target.value,
          );
          onAPIKeyChange(e.target.value);
        }}
        endContent={
          <button
            className="focus:outline-none"
            type="button"
            onClick={onVisibleChange}
          >
            {isVisible ? (
              <FaEye className="text-2xl text-default-400 pointer-events-none" />
            ) : (
              <FaEyeSlash className="text-2xl text-default-400 pointer-events-none" />
            )}
          </button>
        }
      />
      <AutocompleteCombobox
        ariaLabel="agent"
        items={agents.map((agent) => ({ value: agent, label: agent }))}
        defaultKey={settings.AGENT || agents[0]}
        onChange={onAgentChange}
        tooltip={t(I18nKey.SETTINGS$AGENT_TOOLTIP)}
        disabled={disabled}
      />
      <AutocompleteCombobox
        ariaLabel="language"
        items={AvailableLanguages}
        defaultKey={settings.LANGUAGE || "en"}
        onChange={onLanguageChange}
        tooltip={t(I18nKey.SETTINGS$LANGUAGE_TOOLTIP)}
        disabled={disabled}
      />
    </>
  );
}

export default SettingsForm;
