// Native importer smoke test: preserve triangle count and full kilometre extent.
#include <gz/common/MeshManager.hh>
#include <gz/common/Mesh.hh>
#include <iostream>
#include <cmath>

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  const auto mesh = gz::common::MeshManager::Instance()->Load(argv[1]);
  if (!mesh) return 3;
  const auto expected = std::stoul(argv[2]);
  if (mesh->IndexCount() != expected * 3) {
    std::cerr << argv[1] << ": imported " << mesh->IndexCount()
              << " indices, expected " << expected * 3 << '\n';
    return 1;
  }
  if (std::string(argv[1]).find("terrain.dae") != std::string::npos &&
      (std::abs(mesh->Max().X() - mesh->Min().X() - 1000) > .001 ||
       std::abs(mesh->Max().Y() - mesh->Min().Y() - 1000) > .001)) {
    std::cerr << "Imported terrain does not span a kilometre\n";
    return 1;
  }
  std::cout << "Native import OK: " << argv[1] << '\n';
}
