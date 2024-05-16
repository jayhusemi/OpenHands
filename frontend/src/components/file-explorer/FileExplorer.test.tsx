import React from "react";
import { render, waitFor, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react-dom/test-utils";
import { describe, it, expect, vi, Mock } from "vitest";
import FileExplorer from "./FileExplorer";
import { getWorkspace, uploadFiles } from "#/services/fileService";
import toast from "#/utils/toast";

const toastSpy = vi.spyOn(toast, "stickyError");

vi.mock("../../services/fileService", async () => ({
  getWorkspace: vi.fn(async () => ({
    name: "root",
    children: [
      { name: "file1.ts" },
      { name: "folder1", children: [{ name: "file2.ts" }] },
    ],
  })),

  uploadFiles: vi.fn(),
}));

describe("FileExplorer", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should get the workspace directory", async () => {
    const { getByText } = render(<FileExplorer onFileClick={vi.fn} />);

    expect(getWorkspace).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(getByText("root")).toBeInTheDocument();
    });
  });

  it.todo("should render an empty workspace");

  it("calls the onFileClick function when a file is clicked", async () => {
    const onFileClickMock = vi.fn();
    const { getByText } = render(
      <FileExplorer onFileClick={onFileClickMock} />,
    );

    await waitFor(() => {
      expect(getByText("folder1")).toBeInTheDocument();
    });

    act(() => {
      userEvent.click(getByText("folder1"));
    });

    act(() => {
      userEvent.click(getByText("file2.ts"));
    });

    const absPath = "root/folder1/file2.ts";
    expect(onFileClickMock).toHaveBeenCalledWith(absPath);
  });

  it("should refetch the workspace when clicking the refresh button", async () => {
    const onFileClickMock = vi.fn();
    render(<FileExplorer onFileClick={onFileClickMock} />);

    // The 'await' keyword is required here to avoid a warning during test runs
    await act(() => {
      userEvent.click(screen.getByTestId("refresh"));
    });

    expect(getWorkspace).toHaveBeenCalledTimes(2); // 1 from initial render, 1 from refresh button
  });

  it("should toggle the explorer visibility when clicking the close button", async () => {
    const { getByTestId, getByText, queryByText } = render(
      <FileExplorer onFileClick={vi.fn} />,
    );

    await waitFor(() => {
      expect(getByText("root")).toBeInTheDocument();
    });

    act(() => {
      userEvent.click(getByTestId("toggle"));
    });

    // it should be hidden rather than removed from the DOM
    expect(queryByText("root")).toBeInTheDocument();
    expect(queryByText("root")).not.toBeVisible();
  });

  it("should upload files", async () => {
    // TODO: Improve this test by passing expected argument to `uploadFiles`
    const { getByTestId } = render(<FileExplorer onFileClick={vi.fn} />);
    const file = new File([""], "file-name");
    const file2 = new File([""], "file-name-2");

    const uploadFileInput = getByTestId("file-input");

    // The 'await' keyword is required here to avoid a warning during test runs
    await act(() => {
      userEvent.upload(uploadFileInput, file);
    });

    expect(uploadFiles).toHaveBeenCalledOnce();
    expect(getWorkspace).toHaveBeenCalled();

    const uploadDirInput = getByTestId("file-input");

    // The 'await' keyword is required here to avoid a warning during test runs
    await act(() => {
      userEvent.upload(uploadDirInput, [file, file2]);
    });

    expect(uploadFiles).toHaveBeenCalledTimes(2);
    expect(getWorkspace).toHaveBeenCalled();
  });

  it.skip("should upload files when dragging them to the explorer", () => {
    // It will require too much work to mock drag logic, especially for our case
    // https://github.com/testing-library/user-event/issues/440#issuecomment-685010755
    // TODO: should be tested in an e2e environment such as Cypress/Playwright
  });

  it.todo("should download a file");

  it.todo("should display an error toast if file upload fails", async () => {
    (uploadFiles as Mock).mockRejectedValue(new Error());

    const { getByTestId } = render(<FileExplorer onFileClick={vi.fn} />);

    const uploadFileInput = getByTestId("file-input");
    const file = new File([""], "test");

    act(() => {
      userEvent.upload(uploadFileInput, file);
    });

    expect(uploadFiles).rejects.toThrow();
    // TODO: figure out why spy isnt called to pass test
    expect(toastSpy).toHaveBeenCalledWith("ws", "Error uploading file");
  });
});
